# 大麦抢票助手（damai-ticket-helper）

> 一个基于 Appium 的大麦网移动端抢票自动化工具，带可视化图形界面。

**⚠️ 免责声明：本项目仅供技术学习与研究使用，不保证能抢到票，请配合手动抢票。请遵守大麦网及相关平台的使用条款，合理使用，勿用于商业用途。使用本工具产生的任何后果由使用者自行承担。**

---

## 下载使用（推荐）

无需搭建环境，直接下载即用 → [**前往 Releases 下载**](https://github.com/Lzhimie/damai-ticket-helper/releases/latest)

| 文件 | 说明 |
|------|------|
| `damai-ticket-helper-portable-v1.0.0.zip` | 📦 **便携版**（152MB）：含完整环境（Node+Appium+adb），解压即用，无需安装任何软件 |
| `damai-ticket-helper-source-v1.0.0.zip` | 💻 **源码版**（22KB）：仅核心源码，开发者自行搭环境 |

**便携版步骤**：解压 → 手机开USB调试连电脑 → 双击 `抢票助手.exe` → 点红色「一键检测环境」→ 填配置 → 点绿色「开售秒抢」。

> ⚠️ 解压时必须**完整解压整个文件夹**（env 目录是运行环境），不要只拿 exe。
> 文件名用英文是为了兼容各平台下载工具。

---

## 项目来源

本项目基于 [WECENG/ticket-purchase](https://github.com/WECENG/ticket-purchase) 二次开发，感谢原作者的开源贡献。

在原项目（Selenium + Appium 双端抢票）的基础上，新增了：

- ✅ 可视化图形界面（tkinter），一键操作
- ✅ 便携打包（PyInstaller 打包成 exe，环境内置，解压即用）
- ✅ 适配新版大麦 APP（9.x）的界面结构
- ✅ 开售秒抢模式（等待开售/有票，检测到变化瞬间自动抢）
- ✅ 缺货自动刷新（切换场次刷新等待补货）
- ✅ 多观演人自动购票（人数 = 张数，上限 6 张）
- ✅ 间隔自定义（毫秒级调节各步骤速度）

---

## 功能特性

- **双端支持**（继承原项目）：Web 端（Selenium）+ 移动端（Appium）
- **可视化界面**：状态检测、配置编辑、一键启动、实时日志
- **开售秒抢**：毫秒级轮询检测，开售/有票瞬间自动抢
- **缺货刷新**：缺货时自动切换场次刷新，等到有票
- **多观演人**：自动按观演人数设置购票张数
- **循环抢票**：已开售且票抢手时反复重试

---

## 项目结构

```
damai-ticket-helper/
├── damai/                     # Web 端抢票（继承原项目）
│   ├── damai.py
│   └── config.json
├── damai_appium/              # 移动端抢票（核心）
│   ├── damai_app_v2.py        # 主程序
│   ├── damai_app.py           # 原版主程序
│   ├── config.py              # 配置类
│   └── config.example.jsonc   # 配置示例
├── 大麦抢票助手/              # 可视化软件
│   ├── gui_app.py             # GUI 源码
│   ├── 使用说明.txt
│   └── config.example.jsonc   # 配置示例
├── tests/                     # 测试
├── doc/                       # 文档
└── README.md
```

> 注：`env/`（便携环境）、`抢票助手.exe`（打包产物）等二进制/大文件不提交仓库，用户本地自行准备。

---

## 快速开始

### 方式一：源码运行

#### 1. 安装环境

```bash
# Python 3.9+
# Node.js 20.19.0+
# Appium 3.1.0+
npm install -g appium
appium driver install uiautomator2

# Android SDK + 配置环境变量 ANDROID_HOME
```

#### 2. 安装 Python 依赖

```bash
pip install selenium Appium-Python-Client
```

#### 3. 配置

```bash
cd damai_appium
cp config.example.jsonc config.jsonc
# 编辑 config.jsonc 填入演出信息
```

#### 4. 运行

```bash
# 启动 Appium 服务器
appium --port 4999

# 运行抢票（需手机连接 + USB调试 + 安装大麦APP）
python damai_app_v2.py --wait-sale
```

### 方式二：图形界面（推荐）

1. 手机 USB 连接电脑，开启「开发者选项」→「USB 调试」
2. 运行 `gui_app.py`（或使用打包好的 exe）
3. 点红色「一键检测环境」→ 全绿
4. 填好演出配置 → 保存
5. 手机进大麦，停在目标演出页面
6. 点绿色「开售秒抢」挂机等待

---

## 配置说明

| 字段 | 说明 |
|------|------|
| server_url | Appium 服务器地址 |
| keyword | 演出搜索关键词 |
| users | 观演人名单（几个买几张） |
| city | 演出城市 |
| date | 演出日期 |
| session_index | 场次位置（第几个场次卡片，从 0 计数） |
| price | 票价 |
| price_index | 票价位置（第几个票价卡片，从 0 计数） |
| if_commit_order | 是否自动提交订单 |
| delays | 各步骤间隔（秒） |

> **场次/票价位置说明**：大麦新版把日期和票价文字画成了图片，程序读不到，只能按位置点。`session_index` / `price_index` 是「第几个卡片，从 0 开始」。GUI 界面里填的是「第几个，从 1 开始」，会自动转换。

---

## 三大抢票模式

| 模式 | 用途 |
|------|------|
| **开售秒抢** | 等开售/等有票，检测到「立即预定/立即购买」瞬间自动抢（主入口） |
| **循环抢票** | 已开售且票抢手，反复抢到成功为止 |
| （立即抢票已并入秒抢） | — |

### 开售秒抢检测机制

- 每 200ms 轮询按钮文字
- 每 2s 刷新页面（切前后台）+ 点击试探判断状态
- 是「已预约」→ 退回继续刷；是「立即预定」→ 点进去抢
- 缺货 → 切换场次刷新等待补货

---

## 环境要求

- **Python**：3.9+
- **Node.js**：20.19.0+（移动端）
- **Appium**：3.1.0+ + uiautomator2 驱动
- **Android**：真机或模拟器，安装大麦 APP 并登录
- **操作系统**：Windows / macOS / Linux

---

## 常见问题

### 端口 4723 无法绑定

Windows 系统保留端口范围 4658–4757 会占用 4723，本项目已改用 **4999** 端口。

### 服务器「占着端口但无响应」

残留的 node 进程占用了端口，清理后重启：

```bash
# 清理残留进程
taskkill /F /IM node.exe
# 重新启动 Appium
appium --port 4999
```

### 手机识别不到

1. 检查 USB 调试是否开启、USB 模式是否「文件传输」
2. 重新插拔 USB 线，手机弹授权窗口点「始终允许」
3. `adb kill-server && adb start-server` 重启 adb

---

## 许可

本项目仅供学习和研究使用，请勿用于商业用途。请遵守大麦网的使用条款。

基于 [WECENG/ticket-purchase](https://github.com/WECENG/ticket-purchase)，遵循原项目的使用原则。
