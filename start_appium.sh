#!/bin/bash
# 大麦抢票 - Appium启动脚本
# 使用方法: ./start_appium.sh

echo "🚀 启动大麦抢票环境..."

# 设置Android环境变量
export ANDROID_HOME=/Users/shengwang/Library/Android/sdk
export ANDROID_SDK_ROOT=/Users/shengwang/Library/Android/sdk

echo "✅ 环境变量已设置"
echo "   ANDROID_HOME: $ANDROID_HOME"
echo "   ANDROID_SDK_ROOT: $ANDROID_SDK_ROOT"

# 检查Node.js版本
NODE_VERSION=$(node --version | cut -d'v' -f2)
echo "📦 Node.js版本: $NODE_VERSION"

# 检查Appium是否安装
if ! command -v appium &> /dev/null; then
    echo "❌ Appium未安装，请先安装Appium"
    echo "   运行: npm install -g appium"
    exit 1
fi

# 检查Android设备
echo "📱 检查Android设备..."
DEVICES=$(adb devices | grep -c "device$")
if [ $DEVICES -eq 0 ]; then
    echo "⚠️  未检测到Android设备"
    echo "   请启动模拟器或连接真机"
    echo "   启动模拟器: /Users/shengwang/Library/Android/sdk/emulator/emulator -avd Medium_Phone_API_36.0"
    exit 1
else
    echo "✅ 检测到 $DEVICES 个Android设备"
fi

# 检查大麦APP是否安装
if ! adb shell pm list packages | grep -q "cn.damai"; then
    echo "⚠️  大麦APP未安装"
    echo "   请在设备上安装大麦APP"
    exit 1
else
    echo "✅ 大麦APP已安装"
fi

# 启动Appium服务器
echo "🚀 启动Appium服务器..."
echo "   服务器地址: http://127.0.0.1:4723"
echo "   按 Ctrl+C 停止服务器"
echo ""

appium --port 4723
