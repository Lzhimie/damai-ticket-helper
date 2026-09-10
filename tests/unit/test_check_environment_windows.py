import sys
from pathlib import Path
from types import SimpleNamespace

from damai import check_environment


WINDOWS_CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WINDOWS_CHROMEDRIVER = r"C:\Tools\chromedriver.exe"


def test_check_chrome_detects_windows_program_files_install(monkeypatch):
    """Chrome installed in Program Files should be detected on Windows."""

    def fake_exists(path):
        return path == WINDOWS_CHROME

    def fake_version(command):
        if command[0] == WINDOWS_CHROME:
            return "Google Chrome 136.0.7103.114"
        return None

    monkeypatch.setattr(check_environment.os.path, "exists", fake_exists)
    monkeypatch.setattr(check_environment, "_run_command_get_version", fake_version)

    assert check_environment.check_chrome() is True


def test_check_version_match_uses_windows_chrome_and_driver_paths(monkeypatch):
    """Version matching should work for Windows Chrome and chromedriver.exe."""

    def fake_exists(path):
        return path in {WINDOWS_CHROME, WINDOWS_CHROMEDRIVER}

    def fake_islink(path):
        return False

    def fake_version(command):
        if command[0] == WINDOWS_CHROME:
            return "Google Chrome 136.0.7103.114"
        if command[0] == WINDOWS_CHROMEDRIVER:
            return "ChromeDriver 136.0.7103.114"
        return None

    monkeypatch.setenv("CHROMEDRIVER_PATH", WINDOWS_CHROMEDRIVER)
    monkeypatch.setattr(check_environment.os.path, "exists", fake_exists)
    monkeypatch.setattr(check_environment.os.path, "islink", fake_islink)
    monkeypatch.setattr(check_environment, "_run_command_get_version", fake_version)

    assert check_environment.check_version_match() is True


def test_find_chrome_reads_windows_install_version_directory(monkeypatch, tmp_path):
    """
    On Windows, chrome.exe --version can open an existing browser session instead
    of printing a version, so fall back to the versioned install directory.
    """
    chrome_path = str(tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe")
    version_dir = Path(chrome_path).parent / "136.0.7103.114"

    def fake_exists(path):
        return path == chrome_path

    def fake_listdir(path):
        if path == str(Path(chrome_path).parent):
            return [version_dir.name]
        return []

    def fake_isdir(path):
        return path == str(version_dir)

    monkeypatch.setattr(check_environment, "_get_chrome_paths", lambda: [chrome_path], raising=False)
    monkeypatch.setattr(check_environment.os.path, "exists", fake_exists)
    monkeypatch.setattr(check_environment.os.path, "isdir", fake_isdir)
    monkeypatch.setattr(check_environment.os, "listdir", fake_listdir)
    monkeypatch.setattr(check_environment, "_run_command_get_version", lambda command: "正在现有的浏览器会话中打开。")

    assert check_environment._find_chrome() == (
        chrome_path,
        "Google Chrome 136.0.7103.114",
        "136",
    )


def test_get_chromedriver_paths_includes_autoinstaller_cache(monkeypatch, tmp_path):
    """Environment checks should find drivers downloaded by chromedriver-autoinstaller."""
    package_dir = tmp_path / "chromedriver_autoinstaller"
    driver_dir = package_dir / "136"
    driver_dir.mkdir(parents=True)
    driver_path = driver_dir / "chromedriver.exe"
    driver_path.write_text("")

    fake_autoinstaller = SimpleNamespace(__file__=str(package_dir / "__init__.py"))
    monkeypatch.setitem(sys.modules, "chromedriver_autoinstaller", fake_autoinstaller)

    assert str(driver_path) in check_environment._get_chromedriver_paths()
