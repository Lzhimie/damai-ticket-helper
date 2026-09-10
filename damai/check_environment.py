#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
环境检查脚本
在运行抢票脚本前，使用此脚本检查环境是否配置正确
"""

import os
import re
import shutil
import subprocess
import sys


def _get_version_from_output(output):
    """从命令输出中提取主版本号"""
    match = re.search(r'(\d+)\.', output)
    return match.group(1) if match else None


def _run_command_get_version(command):
    """运行命令并获取版本信息"""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            errors="replace",
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return (result.stdout or result.stderr).strip()
    except Exception:
        pass
    return None


def _unique_paths(paths):
    """保持顺序去重，并忽略空路径。"""
    unique = []
    seen = set()
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _get_chrome_paths():
    """返回常见平台上的 Chrome 可执行文件候选路径。"""
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LOCALAPPDATA")

    paths = [
        os.environ.get("CHROME_PATH"),
        os.environ.get("GOOGLE_CHROME_BIN"),
        os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe") if local_appdata else None,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]

    for command in [
        "chrome.exe",
        "chrome",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ]:
        paths.append(shutil.which(command))

    return _unique_paths(paths)


def _get_chromedriver_paths():
    """返回常见平台上的 ChromeDriver 候选路径。"""
    paths = [
        os.environ.get("CHROMEDRIVER_PATH"),
        os.environ.get("SELENIUM_DRIVER_PATH"),
        shutil.which("chromedriver.exe"),
        shutil.which("chromedriver"),
        os.path.join(os.getcwd(), "chromedriver.exe"),
        os.path.join(os.getcwd(), "chromedriver"),
        "/opt/homebrew/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/opt/homebrew/Caskroom/chromedriver",
    ]

    try:
        import chromedriver_autoinstaller
        package_dir = os.path.dirname(chromedriver_autoinstaller.__file__)
        for name in os.listdir(package_dir):
            driver_dir = os.path.join(package_dir, name)
            if os.path.isdir(driver_dir):
                paths.append(os.path.join(driver_dir, "chromedriver.exe"))
                paths.append(os.path.join(driver_dir, "chromedriver"))
    except (AttributeError, ImportError, OSError):
        pass

    return _unique_paths(paths)


def _version_sort_key(version):
    return tuple(int(part) for part in version.split("."))


def _get_windows_chrome_version(chrome_path):
    """Windows 上 chrome.exe --version 可能被已有会话吞掉，改从安装目录读取版本。"""
    app_dir = os.path.dirname(chrome_path)
    try:
        version_dirs = [
            name for name in os.listdir(app_dir)
            if re.fullmatch(r"\d+(?:\.\d+){1,3}", name)
            and os.path.isdir(os.path.join(app_dir, name))
        ]
    except OSError:
        version_dirs = []

    if version_dirs:
        return sorted(version_dirs, key=_version_sort_key)[-1]

    try:
        import winreg
    except ImportError:
        return None

    registry_locations = [
        (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Google\Chrome\BLBeacon"),
    ]
    for hive, key_path in registry_locations:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                version, _ = winreg.QueryValueEx(key, "version")
                if version:
                    return version
        except OSError:
            continue
    return None


def _find_chrome():
    """查找 Chrome，返回 (path, version_str, major_version)。"""
    for chrome_path in _get_chrome_paths():
        if os.path.exists(chrome_path):
            version_str = _run_command_get_version([chrome_path, "--version"])
            if version_str:
                chrome_version = _get_version_from_output(version_str)
                if chrome_version:
                    return chrome_path, version_str, chrome_version

            windows_version = _get_windows_chrome_version(chrome_path)
            if windows_version:
                return chrome_path, f"Google Chrome {windows_version}", _get_version_from_output(windows_version)

    return None, None, None


def check_python_version():
    """检查 Python 版本"""
    print("Python 版本检查...")
    version = sys.version_info
    print(f"  当前版本: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("  ✗ 需要 Python 3.7 或更高版本")
        return False
    print("  ✓ Python 版本符合要求\n")
    return True


def check_dependencies():
    """检查依赖包"""
    print("依赖包检查...")
    dependencies = {
        'selenium': 'Selenium WebDriver',
        'webdriver_manager': 'WebDriver Manager',
    }

    missing = []
    for package, description in dependencies.items():
        try:
            __import__(package)
            print(f"  ✓ {description} ({package})")
        except ImportError:
            print(f"  ✗ {description} ({package}) 未安装")
            missing.append(package)

    if missing:
        print(f"\n  安装命令: pip install {' '.join(missing)}\n")
        return False
    print()
    return True


def check_chrome():
    """检查 Chrome 浏览器"""
    print("Chrome 浏览器检查...")
    chrome_path, version_str, chrome_version = _find_chrome()
    if chrome_path:
        print(f"  ✓ Chrome 浏览器: {version_str}")
        print(f"  ✓ 主版本号: {chrome_version}")
        print(f"  ✓ 路径: {chrome_path}")
        print()
        return True

    print("  ✗ 未找到 Chrome 浏览器")
    print("  请安装 Chrome: https://www.google.com/chrome/")
    print()
    return False


def check_chromedriver():
    """检查 ChromeDriver"""
    print("ChromeDriver 检查...")
    for driver_path in _get_chromedriver_paths():
        if os.path.exists(driver_path) or os.path.islink(driver_path):
            version_str = _run_command_get_version([driver_path, "--version"])
            if version_str:
                driver_version = _get_version_from_output(version_str)
                if driver_version:
                    print(f"  ✓ ChromeDriver: {version_str}")
                    print(f"  ✓ 主版本号: {driver_version}")
                    print(f"  ✓ 路径: {driver_path}")
                    print()
                    return True

    print("  ⚠ 未找到 ChromeDriver")
    print("  安装方法:")
    print("    - macOS: brew install --cask chromedriver")
    print("    - Windows/macOS/Linux: 使用脚本自动安装 chromedriver-autoinstaller")
    print("    - 或手动下载: https://googlechromelabs.github.io/chrome-for-testing/")
    print()
    return False


def check_version_match():
    """检查 Chrome 和 ChromeDriver 版本是否匹配"""
    print("版本匹配检查...")

    _, _, chrome_version = _find_chrome()

    driver_version = None
    for driver_path in _get_chromedriver_paths():
        if os.path.exists(driver_path) or os.path.islink(driver_path):
            version_str = _run_command_get_version([driver_path, "--version"])
            if version_str:
                driver_version = _get_version_from_output(version_str)
                break

    if not chrome_version or not driver_version:
        print("  ⚠ 无法获取版本信息")
        print()
        return False

    print(f"  Chrome 版本: {chrome_version}")
    print(f"  ChromeDriver 版本: {driver_version}")

    if chrome_version == driver_version:
        print("  ✓ 版本匹配")
        print()
        return True
    else:
        print(f"  ✗ 版本不匹配！(差距: {abs(int(chrome_version) - int(driver_version))} 个主版本)")
        print("\n  解决方案:")
        print("  方案1: 更新 Chrome 浏览器到最新版本（推荐）")
        print("    打开 Chrome → 设置 → 关于 Chrome → 等待更新")
        print()
        print("  方案2: 安装匹配的 ChromeDriver")
        print("    卸载当前版本: brew uninstall --cask chromedriver")
        print("    手动下载: https://googlechromelabs.github.io/chrome-for-testing/")
        print()
        return False


def get_chromedriver_path():
    """
    获取 ChromeDriver 路径，如果不存在则自动安装。
    供其他脚本导入使用。
    :return: ChromeDriver 可执行文件路径
    """
    _, _, chrome_version = _find_chrome()

    if chrome_version:
        for driver_path in _get_chromedriver_paths():
            if os.path.exists(driver_path) or os.path.islink(driver_path):
                driver_version_str = _run_command_get_version([driver_path, "--version"])
                if driver_version_str:
                    driver_version = _get_version_from_output(driver_version_str)
                    if driver_version == chrome_version:
                        return driver_path

        print(f"  Chrome 版本: {chrome_version}")
    else:
        print("  ⚠ 未通过常见路径检测到 Chrome，尝试使用 chromedriver-autoinstaller 自动检测...")

    print("  正在自动安装匹配的 ChromeDriver...")
    try:
        import chromedriver_autoinstaller
        chromedriver_path = chromedriver_autoinstaller.install()

        result = _run_command_get_version([chromedriver_path, "--version"])
        if not result:
            raise RuntimeError("ChromeDriver 无法执行")

        print(f"  ✓ ChromeDriver 安装成功: {result}")
        return chromedriver_path
    except ImportError:
        raise RuntimeError("未安装 chromedriver-autoinstaller，请运行: pip install chromedriver-autoinstaller")
    except Exception as e:
        raise RuntimeError(f"ChromeDriver 安装失败: {e}")


def check_config_file():
    """检查配置文件"""
    print("配置文件检查...")
    config_file = 'config.json'

    if not os.path.exists(config_file):
        print(f"  ✗ 未找到配置文件: {config_file}")
        print(f"  请先创建配置文件")
        print()
        return False

    try:
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"  ✓ 配置文件存在: {config_file}")

        required_fields = ['index_url', 'login_url', 'target_url', 'users']
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            print(f"  ✗ 缺少必需字段: {', '.join(missing_fields)}")
            print()
            return False

        print(f"  ✓ 必需字段完整")
        print(f"  ✓ 观众人数: {len(config['users'])} 人")
        print()
        return True
    except Exception as e:
        print(f"  ✗ 配置文件错误: {e}")
        print()
        return False


def main():
    print("\n" + "=" * 60)
    print("大麦抢票脚本 - 环境检查工具")
    print("=" * 60)
    print()

    checks = [
        ("Python 版本", check_python_version),
        ("依赖包", check_dependencies),
        ("Chrome 浏览器", check_chrome),
        ("ChromeDriver", check_chromedriver),
        ("版本匹配", check_version_match),
        ("配置文件", check_config_file),
    ]

    results = []
    for name, check_func in checks:
        try:
            results.append((name, check_func()))
        except Exception as e:
            print(f"  ✗ 检查出错: {e}\n")
            results.append((name, False))

    print("=" * 60)
    print("检查结果汇总")
    print("=" * 60)

    all_passed = all(result for _, result in results)
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")

    print("=" * 60)

    if all_passed:
        print("\n✓ 所有检查通过！可以运行抢票脚本了。")
        print("  运行命令: python damai.py\n")
        return 0
    else:
        print("\n✗ 部分检查未通过，请根据上述提示修复问题。\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
