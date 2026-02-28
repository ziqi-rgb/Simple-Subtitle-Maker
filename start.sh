#!/bin/bash
# =================================================================
# Whisper GUI Subtitle Tool - 启动脚本
# =================================================================

# 检查虚拟环境是否存在
if [ ! -f "venv/bin/activate" ]; then
    echo "错误: 未找到虚拟环境!"
    echo "请先运行 \"./install.sh\" 来完成安装。"
    exit 1
fi

# 激活虚拟环境
source "venv/bin/activate"

# 启动主程序
echo "正在启动 Whisper GUI Subtitle Tool..."
python3 main.py

exit 0