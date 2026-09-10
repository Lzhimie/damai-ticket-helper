# -*- coding: UTF-8 -*-
"""大麦抢票助手 - 图形界面（打包版：双击抢票助手.exe 即用）"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

APP_TITLE = "大麦抢票助手"
PORT = 4999

# 间隔设置默认值（秒），与脚本 config.py 保持一致
DEFAULT_DELAYS = {
    "poll": 0.2,       # 开售检测轮询间隔
    "refresh": 2.0,    # 页面强制刷新间隔
    "step": 0.5,       # 步骤间间隔
    "click": 0.15,     # 连续点击间隔
    "scroll": 0.6,     # 滚动后等待
    "page_load": 2.5,  # 页面加载等待
}

# ---------- 路径：区分打包(exe)运行 与 源码运行 ----------
def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

ROOT = app_dir()
ENV = os.path.join(ROOT, 'env')
NODE = os.path.join(ENV, 'node', 'node.exe')
APPIUM_JS = os.path.join(ENV, 'appium', 'build', 'lib', 'main.js')
APPIUM_HOME = os.path.join(ENV, 'appium-home')
ADB = os.path.join(ENV, 'platform-tools', 'adb.exe')
PLATFORM_TOOLS = os.path.join(ENV, 'platform-tools')

if getattr(sys, 'frozen', False):
    SCRIPT_WORKDIR = ROOT          # 打包：配置文件放在 exe 旁
else:
    SCRIPT_WORKDIR = os.path.join(os.path.dirname(ROOT), 'damai_appium')   # 源码：用仓库里的现有配置
    sys.path.insert(0, SCRIPT_WORKDIR)

CONFIG_FILE = os.path.join(SCRIPT_WORKDIR, 'config.jsonc')
os.chdir(SCRIPT_WORKDIR)


class GrabbingApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("880x720")
        self.root.minsize(780, 620)

        self.appium_proc = None
        self.grab_thread = None
        self.grab_stop = threading.Event()
        self.log_queue = queue.Queue()
        self.delay_defaults_ms = {}

        self._build_ui()
        self.root.after(100, self._poll_log_queue)
        self.refresh_status()

    # ---------- 界面 ----------
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('vista')
        except Exception:
            pass

        self._font_registry = []   # (widget, base_size, bold)
        self._resize_job = None

        def reg(w, size=9, bold=False):
            self._font_registry.append((w, size, bold))
            return w

        def L(parent, text, size=9, bold=False, fg=None):
            lbl = ttk.Label(parent, text=text)
            if fg:
                lbl.configure(foreground=fg)
            return reg(lbl, size, bold)

        # ===== 主布局：grid（缩放时按比例伸缩，不隐藏控件）=====
        self.root.grid_columnconfigure(0, weight=0, minsize=250)  # 左侧注意事项
        self.root.grid_columnconfigure(1, weight=1)               # 主区域
        self.root.grid_rowconfigure(0, weight=0)                  # 顶部红色横幅
        self.root.grid_rowconfigure(1, weight=1)                  # 内容区

        # 顶部红色大字横幅（居中）
        banner = ttk.Label(self.root, text="不保证能抢到票!!要配合手动抢",
                           foreground="#c62828", anchor="center",
                           font=("Microsoft YaHei", 16, "bold"))
        self._font_registry.append((banner, 16, True))
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=6)

        # 左侧注意事项（红字竖排，详细步骤）
        notes = ttk.LabelFrame(self.root, text="注意事项", padding=6)
        notes.grid(row=1, column=0, sticky="nsw", padx=(10, 4), pady=6)
        notes.grid_columnconfigure(0, weight=1)
        notes.grid_rowconfigure(0, weight=1)
        self._notes_text = reg(tk.Text(notes, width=30, height=22, wrap="word",
                                       state="disabled", relief="flat",
                                       font=("Microsoft YaHei", 9)), size=9)
        self._notes_text.grid(row=0, column=0, sticky="nsew")
        self._notes_text.tag_configure("red", foreground="#c62828")
        self._notes_text.tag_configure("head", foreground="#c62828",
                                       font=("Microsoft YaHei", 9, "bold"))
        notes_content = (
            "【使用前准备】\n"
            "① USB连接：手机用数据线连电脑\n"
            "② 开发者模式：设置→关于手机→"
            "连续点击「版本号」7次\n"
            "③ USB调试：设置→开发者选项→"
            "打开「USB调试」开关\n"
            "④ 授权：连电脑后手机弹出授权窗口，"
            "勾选「始终允许」并点「允许」\n"
            "⑤ 装APP：手机上安装大麦APP并登录账号\n\n"
            "【每次使用】\n"
            "⑥ 点红色「一键检测环境」自动检查+适配手机+启动服务器\n"
            "⑦ 手机进入大麦，停在目标演出的页面"
            "（详情页或选票页均可）\n"
            "⑧ 点绿色「开售秒抢」等待开售/等有票，"
            "状态一变瞬间自动抢\n"
            "⑨ 跳转支付宝后，手动完成付款锁票\n\n"
            "【提醒】\n"
            "⑩ 等待期间手机保持亮屏、USB不要拔\n"
            "⑪ 识别不到手机：换数据线/USB口，"
            "或安装手机品牌USB驱动\n"
            "⑫ 换场次务必改对「场次位置」「票价位置」\n"
        )
        self._notes_text.configure(state="normal")
        for line in notes_content.split("\n"):
            tag = "head" if line.startswith("【") else "red"
            self._notes_text.insert("end", line + "\n", tag)
        self._notes_text.configure(state="disabled")

        # 主区域容器
        main = ttk.Frame(self.root)
        main.grid(row=1, column=1, sticky="nsew", padx=(4, 10), pady=6)
        main.grid_columnconfigure(0, weight=1)
        for r in range(4):
            main.grid_rowconfigure(r, weight=0)
        main.grid_rowconfigure(4, weight=1)  # 日志行伸缩

        # ---- 状态区 ----
        top = ttk.LabelFrame(main, text="状态", padding=8)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self.lbl_server = L(top, "Appium服务器: 检测中...")
        self.lbl_server.grid(row=0, column=0, sticky="w", padx=6)
        self.lbl_device = L(top, "手机: 检测中...")
        self.lbl_device.grid(row=1, column=0, sticky="w", padx=6)
        self.lbl_damai = L(top, "大麦APP: 检测中...")
        self.lbl_damai.grid(row=2, column=0, sticky="w", padx=6)
        # 状态区右侧按钮（红：先点这个!!!）
        top_btns = ttk.Frame(top)
        top_btns.grid(row=0, column=1, rowspan=3, sticky="ne", padx=4)
        check_box = ttk.Frame(top_btns)
        check_box.pack(side="top", padx=4, pady=2)
        L(check_box, "先点这个!!!", size=9, bold=True, fg="#c62828").pack()
        self.btn_check = reg(tk.Button(check_box, text="一键检测环境",
                                       bg="#e53935", fg="white", activebackground="#c62828",
                                       activeforeground="white", relief="raised", bd=1,
                                       font=("Microsoft YaHei", 9),
                                       command=self.check_env), size=9)
        self.btn_check.pack()
        self.btn_server = reg(ttk.Button(top_btns, text="启动Appium服务器", command=self.toggle_server), size=9)
        self.btn_server.pack(side="top", padx=4, pady=2)
        reg(ttk.Button(top_btns, text="刷新状态", command=self.refresh_status), size=9).pack(side="top", padx=4, pady=2)

        # ---- 抢票配置 ----
        cfg = ttk.LabelFrame(main, text="抢票配置", padding=8)
        cfg.grid(row=1, column=0, sticky="ew")
        grid = ttk.Frame(cfg)
        grid.pack(anchor="w")   # 左对齐、自然宽度，标签不被挤
        self.vars = {}
        fields = [
            ("keyword", "演出关键词"),
            ("city", "城市"),
            ("date", "日期(如9.25)"),
            ("session_index", "场次位置(第几个,从1)"),
            ("price", "票价(如380)"),
            ("price_index", "票价位置(第几个,从1)"),
        ]
        for i, (key, label) in enumerate(fields):
            L(grid, label, size=9).grid(row=i // 3, column=(i % 3) * 2, sticky="w", padx=4, pady=3)
            var = tk.StringVar()
            ent = reg(ttk.Entry(grid, textvariable=var, width=9), size=9)
            ent.grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=4, pady=3)
            self.vars[key] = var
        L(grid, "观演人(逗号分隔)", size=9).grid(row=2, column=0, sticky="w", padx=4, pady=3)
        self.vars["users"] = tk.StringVar()
        reg(ttk.Entry(grid, textvariable=self.vars["users"], width=24), size=9).grid(
            row=2, column=1, columnspan=3, sticky="w", padx=4, pady=3)
        L(grid, "自动提交订单", size=9).grid(row=2, column=4, sticky="w", padx=4)
        self.vars["if_commit_order"] = tk.BooleanVar(value=True)
        reg(ttk.Checkbutton(grid, text="", variable=self.vars["if_commit_order"]), size=9).grid(row=2, column=5, sticky="w")
        btns = ttk.Frame(cfg)
        btns.pack(fill="x", pady=4)
        reg(ttk.Button(btns, text="保存配置", command=self.save_config), size=9).pack(side="left", padx=4)
        reg(ttk.Button(btns, text="读取配置", command=self.load_config), size=9).pack(side="left", padx=4)

        # ---- 抢票操作 ----
        act = ttk.LabelFrame(main, text="抢票操作", padding=8)
        act.grid(row=2, column=0, sticky="ew")
        # 开售秒抢：绿色高亮 + 上方提示（唯一抢票入口，有票/等票都用它）
        wait_box = ttk.Frame(act)
        wait_box.pack(side="left", padx=8, pady=2)
        L(wait_box, "抢票前5分钟开启", size=9, bold=True, fg="#c62828").pack()
        L(wait_box, "一般用这个", size=9, bold=True, fg="#2e7d32").pack()
        self.btn_wait = reg(tk.Button(wait_box, text="开售秒抢(等开售/等有票·自动刷新)",
                                      bg="#4CAF50", fg="white", activebackground="#388E3C",
                                      activeforeground="white", relief="raised", bd=1,
                                      font=("Microsoft YaHei", 9),
                                      command=lambda: self.start_grab('wait_sale')), size=9)
        self.btn_wait.pack()
        self.btn_loop = reg(ttk.Button(act, text="循环抢票", command=lambda: self.start_grab('loop')), size=9)
        self.btn_loop.pack(side="left", padx=8, pady=4)
        self.btn_stop = reg(ttk.Button(act, text="停止", command=self.stop_grab, state="disabled"), size=9)
        self.btn_stop.pack(side="left", padx=8, pady=4)

        # ---- 间隔设置 ----
        dl = ttk.LabelFrame(main, text="间隔设置(毫秒) - 可自定义各步骤速度", padding=8)
        dl.grid(row=3, column=0, sticky="ew")
        dlg = ttk.Frame(dl)
        dlg.pack(anchor="w")
        self.delay_vars = {}
        delay_fields = [
            ("poll", "开售检测轮询(毫秒)", 200),
            ("refresh", "页面刷新(毫秒)", 2000),
            ("step", "步骤间隔(毫秒)", 500),
            ("click", "连续点击(毫秒)", 150),
            ("scroll", "滚动等待(毫秒)", 600),
            ("page_load", "页面加载(毫秒)", 2500),
        ]
        for i, (key, label, default_ms) in enumerate(delay_fields):
            L(dlg, label, size=9).grid(row=i // 3, column=(i % 3) * 2, sticky="w", padx=4, pady=2)
            var = tk.StringVar()
            ent = reg(ttk.Entry(dlg, textvariable=var, width=7), size=9)
            ent.grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=4, pady=2)
            self.delay_vars[key] = var
            self.delay_defaults_ms[key] = default_ms
        dl_btns = ttk.Frame(dl)
        dl_btns.pack(fill="x", pady=2)
        reg(ttk.Button(dl_btns, text="保存间隔设置", command=self.save_config), size=9).pack(side="right", padx=4)
        reg(ttk.Button(dl_btns, text="恢复默认间隔", command=self.reset_delays), size=9).pack(side="right", padx=4)
        L(dl_btns, "提示: 抢票时机紧张调小，手机卡顿调大", size=9, fg="#888").pack(side="left", padx=4)

        # ---- 日志区 ----
        logf = ttk.LabelFrame(main, text="运行日志", padding=4)
        logf.grid(row=4, column=0, sticky="nsew")
        logf.grid_rowconfigure(0, weight=1)
        logf.grid_columnconfigure(0, weight=1)
        self.log = reg(scrolledtext.ScrolledText(logf, height=14, font=("Microsoft YaHei", 9), state="disabled"), size=9)
        self.log.grid(row=0, column=0, sticky="nsew")

        # 窗口缩放 → 字体随窗口缩放（防抖）
        self.root.bind("<Configure>", self._on_resize)
        self.load_config()

    def _on_resize(self, event=None):
        """窗口缩放时触发（防抖后统一缩放字体）"""
        try:
            self.root.after_cancel(self._resize_job)
        except Exception:
            pass
        self._resize_job = self.root.after(120, self._apply_font_scale)

    def _apply_font_scale(self):
        """按窗口宽度比例缩放所有已注册控件的字体（尺寸不变则跳过，防止反馈循环）"""
        w = self.root.winfo_width()
        if w <= 0:
            return
        scale = max(0.65, min(w / 880.0, 2.2))
        new_sizes = {base: max(int(base * scale), 7) for base, _, _ in self._font_registry}
        if new_sizes == getattr(self, '_last_font_sizes', None):
            return
        self._last_font_sizes = new_sizes
        for widget, base, bold in self._font_registry:
            try:
                widget.configure(font=("Microsoft YaHei",
                                       new_sizes[base],
                                       "bold" if bold else "normal"))
            except Exception:
                pass

    # ---------- 日志 ----------
    def append_log(self, text):
        self.log_queue.put(text)

    def _poll_log_queue(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", text)
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def log_line(self, text):
        self.append_log(text + "\n")

    # ---------- 配置 ----------
    def reset_delays(self):
        for key, var in self.delay_vars.items():
            default_ms = self.delay_defaults_ms.get(key, int(DEFAULT_DELAYS.get(key, 0.5) * 1000))
            var.set(str(default_ms))
        self.log_line("[配置] 间隔已恢复默认，记得点保存生效")

    def _detect_device(self):
        """自动检测已连接手机：序列号 + Android版本（便携adb）"""
        try:
            out = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=10,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            for line in out.splitlines()[1:]:
                if line.strip() and "device" in line and "unauthorized" not in line:
                    serial = line.split()[0]
                    ver = subprocess.run([ADB, "-s", serial, "shell", "getprop", "ro.build.version.release"],
                                         capture_output=True, text=True, timeout=10,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
                    return serial, ver
        except Exception:
            pass
        return "", ""

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                c = json.load(f)
            self.vars["keyword"].set(c.get("keyword", ""))
            self.vars["city"].set(c.get("city", ""))
            self.vars["date"].set(c.get("date", ""))
            self.vars["session_index"].set(str(int(c.get("session_index", 0)) + 1))
            self.vars["price"].set(c.get("price", ""))
            self.vars["price_index"].set(str(int(c.get("price_index", 0)) + 1))
            self.vars["users"].set(",".join(c.get("users", [])))
            self.vars["if_commit_order"].set(bool(c.get("if_commit_order", True)))
            # 间隔设置（内部存秒，界面显示毫秒）
            delays = c.get("delays", {})
            for key, var in self.delay_vars.items():
                sec = delays.get(key, DEFAULT_DELAYS.get(key, 0.5))
                var.set(str(int(float(sec) * 1000)))
            # 设备信息缺失时自动检测（打包版必须，否则连不上手机）
            self.device_name = c.get("deviceName", "")
            self.platform_version = c.get("platformVersion", "")
            # 始终以实际连接的手机为准：换手机/换电脑时自动更新设备信息
            serial, ver = self._detect_device()
            if serial and ver and (serial != self.device_name or ver != self.platform_version):
                self.log_line(f"[配置] 检测到设备 {serial} (Android {ver})，已自动更新（原配置: {self.device_name}）")
                self.device_name = serial
                self.platform_version = ver
        except Exception as e:
            self.log_line(f"[配置] 读取失败: {e}")
            self.device_name = ""
            self.platform_version = ""

    def save_config(self, silent=False):
        try:
            users = [u.strip() for u in self.vars["users"].get().split(",") if u.strip()]
            if not self.device_name or not self.platform_version:
                serial, ver = self._detect_device()
                self.device_name = serial or self.device_name
                self.platform_version = ver or self.platform_version
            c = {
                "server_url": f"http://127.0.0.1:{PORT}",
                "deviceName": self.device_name,
                "platformVersion": self.platform_version,
                "keyword": self.vars["keyword"].get().strip(),
                "users": users,
                "city": self.vars["city"].get().strip(),
                "date": self.vars["date"].get().strip(),
                "session_index": max(int(self.vars["session_index"].get() or 1) - 1, 0),
                "price": self.vars["price"].get().strip(),
                "price_index": max(int(self.vars["price_index"].get() or 1) - 1, 0),
                "if_commit_order": bool(self.vars["if_commit_order"].get()),
                "delays": {key: max(float(var.get() or 1), 1) / 1000.0
                           for key, var in self.delay_vars.items()},
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
            self.log_line("[配置] 已保存")
            if not silent:
                messagebox.showinfo(APP_TITLE, "配置已保存")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"保存失败: {e}")

    # ---------- 服务器 ----------
    def server_running(self):
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status", timeout=2) as r:
                return "ready" in r.read().decode("utf-8", "ignore")
        except Exception:
            return False

    def start_server(self):
        if self.server_running():
            self.log_line("[服务器] 已在运行")
            return True
        # 端口被占但服务器无响应：先清理残留的Appium进程，防止启动失败
        if self.appium_proc and self.appium_proc.poll() is None:
            try:
                self.appium_proc.terminate()
                self.log_line("[服务器] 已终止旧的服务器进程")
            except Exception:
                pass
        try:
            subprocess.run(["taskkill", "/F", "/IM", "node.exe"],
                           capture_output=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            time.sleep(1)
            self.log_line("[服务器] 已清理残留的Appium进程")
        except Exception:
            pass
        if not os.path.exists(NODE) or not os.path.exists(APPIUM_JS):
            self.log_line("[服务器] ❌ 未找到便携环境(env目录)，请确认与exe在同一文件夹")
            return False
        env = os.environ.copy()
        env["APPIUM_HOME"] = APPIUM_HOME
        env["ANDROID_HOME"] = PLATFORM_TOOLS
        env["ANDROID_SDK_ROOT"] = PLATFORM_TOOLS
        env["PATH"] = PLATFORM_TOOLS + ";" + env.get("PATH", "")
        cmd = [NODE, APPIUM_JS, "--port", str(PORT), "--address", "127.0.0.1"]
        self.log_line(f"[服务器] 启动中: {cmd[0]}")
        try:
            # 输出写到日志文件（不能接PIPE不读取，会写满缓冲区导致服务器假死）
            server_log = open(os.path.join(ROOT, "appium_server.log"), "a",
                              encoding="utf-8", errors="replace")
            self.appium_proc = subprocess.Popen(
                cmd, env=env, stdout=server_log, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            self.log_line(f"[服务器] 启动失败: {e}")
            return False
        for _ in range(30):
            time.sleep(0.5)
            if self.server_running():
                self.log_line("[服务器] ✅ 已就绪")
                return True
        self.log_line("[服务器] 启动超时，请查看下方日志")
        return False

    def toggle_server(self):
        if self.server_running():
            self.stop_server()
        else:
            self.start_server()
        self.refresh_status()

    def stop_server(self):
        if self.appium_proc and self.appium_proc.poll() is None:
            self.appium_proc.terminate()
            self.log_line("[服务器] 已停止")

    # ---------- 状态 ----------
    def refresh_status(self):
        def work():
            server = self.server_running()
            dev = self._adb_devices()
            damai = self._damai_installed(dev)
            self.root.after(0, lambda: self._update_status_labels(server, dev, damai))
        threading.Thread(target=work, daemon=True).start()

    def _update_status_labels(self, server, dev, damai):
        self.lbl_server.config(text=f"Appium服务器: {'✅ 运行中' if server else '❌ 未运行'}")
        self.lbl_device.config(text=f"手机: {'✅ ' + dev if dev else '❌ 未连接'}")
        self.lbl_damai.config(text=f"大麦APP: {'✅ 已安装' if damai else '❌ 未安装'}")
        self.btn_server.config(text="停止Appium服务器" if server else "启动Appium服务器")

    def _adb_devices(self):
        try:
            out = subprocess.run([ADB, "devices"], capture_output=True, text=True,
                                 timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            for line in out.splitlines()[1:]:
                if line.strip() and "device" in line and "unauthorized" not in line:
                    return line.split()[0]
        except Exception:
            pass
        return ""

    def _damai_installed(self, device):
        if not device:
            return False
        try:
            out = subprocess.run([ADB, "-s", device, "shell", "pm", "list", "packages"],
                                 capture_output=True, text=True, timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            return "cn.damai" in out
        except Exception:
            return False

    def check_env(self):
        """一键检测环境：便携环境/手机/大麦/服务器，自动修复可修复项"""
        self.log_line("========== 一键检测环境 ==========")
        ok = True

        # 1. 便携环境完整性
        env_parts = [("Node", NODE), ("Appium", APPIUM_JS), ("adb", ADB)]
        missing = [name for name, p in env_parts if not os.path.exists(p)]
        if missing:
            self.log_line(f"[1] 便携环境: ❌ 缺少 {', '.join(missing)}")
            self.log_line("    请确认 env 文件夹与「抢票助手.exe」在同一目录（解压完整）")
            ok = False
        else:
            self.log_line("[1] 便携环境(Node/Appium/adb): ✅ 完整")

        # 2. 手机连接
        dev = self._adb_devices()
        if not dev:
            self.log_line("[2] 手机连接: ❌ 未检测到手机")
            self.log_line("    请用USB线连接手机，并在手机上开启「USB调试」")
            self.log_line("    (设置→关于手机→连点版本号7次→开发者选项→USB调试)")
            self.log_line("    连接后手机弹出授权窗口请点「允许」；若识别不到，安装手机品牌USB驱动")
            ok = False
        else:
            self.log_line(f"[2] 手机连接: ✅ {dev}")
            # 3. 设备信息自动更新（换手机自动适配）
            ver = ""
            try:
                ver = subprocess.run([ADB, "-s", dev, "shell", "getprop", "ro.build.version.release"],
                                     capture_output=True, text=True, timeout=10,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
            except Exception:
                pass
            if ver:
                self.device_name = dev
                self.platform_version = ver
                self.log_line(f"[3] 设备信息: ✅ 已自动适配 {dev} (Android {ver})")
            # 4. 大麦APP
            if self._damai_installed(dev):
                self.log_line("[4] 大麦APP: ✅ 已安装")
            else:
                self.log_line("[4] 大麦APP: ❌ 未安装")
                self.log_line("    请在手机上安装大麦APP并登录账号")
                ok = False

        # 5. Appium服务器
        if self.server_running():
            self.log_line("[5] Appium服务器: ✅ 运行中")
        else:
            self.log_line("[5] Appium服务器: ❌ 未运行，正在自动启动...")
            if self.start_server():
                self.log_line("[5] Appium服务器: ✅ 已启动")
            else:
                self.log_line("[5] Appium服务器: ❌ 启动失败，请检查env文件夹")
                ok = False

        # 6. 保存自动适配的设备信息
        if self.device_name and self.platform_version:
            try:
                self.save_config(silent=True)
            except Exception:
                pass

        if ok:
            self.log_line("========== ✅ 环境全部就绪，可以开始抢票 ==========")
            messagebox.showinfo(APP_TITLE, "环境检测通过！\n配置已就绪，可以开始抢票")
        else:
            self.log_line("========== ⚠️ 有项目未通过，请按上面提示处理 ==========")
            messagebox.showwarning(APP_TITLE, "环境检测有未通过项\n请查看日志中的提示")

    # ---------- 抢票 ----------
    def start_grab(self, mode):
        if self.grab_thread and self.grab_thread.is_alive():
            self.log_line("⚠️ 已有抢票任务在运行！请先点「停止」再开始新的")
            return
        mode_name = {'once': '立即抢票', 'wait_sale': '开售秒抢', 'loop': '循环抢票'}.get(mode, mode)
        self.log_line(f"[抢票] 已点击「{mode_name}」，正在启动...")
        self.grab_stop.clear()
        self.btn_stop.config(state="normal")
        self.btn_wait.config(state="disabled")
        self.btn_loop.config(state="disabled")
        self.grab_thread = threading.Thread(target=self._grab_worker, args=(mode,), daemon=True)
        self.grab_thread.start()
        self.log_line(f"[抢票] {mode_name} 已开始，日志如下（手机请保持亮屏）")

    def stop_grab(self):
        self.grab_stop.set()
        self.log_line("[抢票] 已请求停止（当前步骤完成后退出）")

    def _grab_worker(self, mode):
        # 捕获 print 输出到界面
        real_stdout = sys.stdout
        sys.stdout = _Tee(real_stdout, self.append_log)
        try:
            # 服务器未运行时自动启动（在后台线程执行，不卡界面）
            if not self.server_running():
                self.append_log("[抢票] Appium服务器未运行，正在自动启动...\n")
                if not self.start_server():
                    self.append_log("[抢票] 服务器启动失败，无法开始\n")
                    return
            import damai_app_v2
            while not self.grab_stop.is_set():
                self.append_log(f"\n======= {time.strftime('%H:%M:%S')} =======\n")
                bot = damai_app_v2.DamaiBot()
                try:
                    if mode == 'wait_sale':
                        ok = bot.run_wait_sale(stop_event=self.grab_stop)
                        break
                    elif mode == 'loop':
                        # 循环前检查：页面不匹配或预约状态 → 停止循环并明确提示（重试无意义）
                        try:
                            if not bot._check_show_match():
                                self.append_log("\n⚠️ 循环抢票停止：当前页面与配置的演出不匹配！\n")
                                self.append_log(f"   配置: {bot.config.keyword} / {bot.config.city}\n")
                                self.append_log("   请先在手机上进入正确演出的页面，再重新点「循环抢票」\n")
                                break
                            if bot._is_reserve_state():
                                self.append_log("\n⚠️ 循环抢票停止：当前为预约/未开售状态，无法下单！\n")
                                self.append_log("   请使用「开售秒抢」模式等待开售瞬间自动抢\n")
                                break
                        except Exception as e:
                            self.append_log(f"[循环] 页面检查异常: {e}\n")
                        ok = bot.run_with_retry()
                        if ok:
                            self.append_log("\n[抢票] 本轮成功！已停止（防止重复下单）\n")
                            break
                        time.sleep(0.5)
                    else:
                        ok = bot.run_with_retry()
                        break
                finally:
                    try:
                        bot.driver.quit()
                    except Exception:
                        pass
        except Exception as e:
            self.append_log(f"[抢票] 异常: {e}\n")
        finally:
            sys.stdout = real_stdout
            self.root.after(0, self._grab_done)

    def _grab_done(self):
        self.btn_stop.config(state="disabled")
        self.btn_wait.config(state="normal")
        self.btn_loop.config(state="normal")
        self.append_log("\n[抢票] 任务结束\n")


class _Tee:
    """把 print 输出同时送到界面日志"""
    def __init__(self, real, callback):
        self.real = real
        self.cb = callback

    def write(self, s):
        if s.strip():
            self.cb(s)
        try:
            self.real.write(s)
        except Exception:
            pass

    def flush(self):
        try:
            self.real.flush()
        except Exception:
            pass


def main():
    root = tk.Tk()
    app = GrabbingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
