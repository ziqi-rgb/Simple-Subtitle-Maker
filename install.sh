#!/bin/bash

# =================================================================
# Whisper GUI Subtitle Tool - 自动安装脚本
# =================================================================

echo ""
echo " 欢迎使用 Whisper GUI Subtitle Tool 安装程序"
echo " ================================================"
echo ""
echo " 此脚本将自动完成以下操作:"
echo " 1. 检查 Python 环境"
echo " 2. 创建独立的虚拟环境 (venv)"
echo " 3. 检查 NVIDIA CUDA 并确定 PyTorch 版本"
echo " 4. 自动切换镜像源 (如果需要)"
echo " 5. 安装所有必需的 Python 依赖库"
echo ""

read -p "按 Enter 键继续..."

# 步骤 1: 检查 Python 环境
echo "[1/5] 正在检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo ""
    echo " 错误: 未找到 python3!"
    echo " 请先安装 Python 3.8 或更高版本。"
    echo ""
    exit 1
fi
echo " Python 环境正常。"
echo ""

# 步骤 2: 创建虚拟环境
echo "[2/5] 正在准备虚拟环境..."
if [ ! -d "venv" ]; then
    echo " 正在创建新的虚拟环境 (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo " 错误: 创建虚拟环境失败。"
        exit 1
    fi
else
    echo " 已找到现有的虚拟环境 (venv)。"
fi
echo " 虚拟环境准备就绪。"
echo ""

# 激活虚拟环境以进行后续操作
source venv/bin/activate

# 步骤 3: 检查 CUDA 并确定 PyTorch 版本
echo "[3/5] 正在检测 NVIDIA CUDA 并配置 PyTorch..."
PYTORCH_CMD="pip install torch"
if command -v nvidia-smi &> /dev/null; then
    echo " 检测到 NVIDIA 显卡驱动。正在查询 CUDA 版本..."
    CUDA_VERSION=$(nvidia-smi --query-gpu=cuda_version --format=csv,noheader)
    
    echo " 检测到的 CUDA 版本: $CUDA_VERSION"
    
    CUDA_MAJOR=$(echo $CUDA_VERSION | cut -d'.' -f1)

    if [ "$CUDA_MAJOR" = "12" ]; then
        echo " 配置为安装 CUDA 12.1 对应的 PyTorch。"
        PYTORCH_CMD="pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
    elif [ "$CUDA_MAJOR" = "11" ]; then
        echo " 配置为安装 CUDA 11.8 对应的 PyTorch。"
        PYTORCH_CMD="pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118"
    else
        echo " 警告: 未知的 CUDA 版本 ($CUDA_VERSION)，将安装 CPU 版本的 PyTorch。"
    fi
else
    echo " 未检测到 NVIDIA 显卡或 nvidia-smi。将安装 CPU 版本的 PyTorch。"
fi
echo ""

# 步骤 4: 检查网络并选择镜像源
echo "[4/5] 正在测试网络连接以选择最佳下载源..."
PIP_OPTIONS=""
if ! ping -c 1 pypi.org &> /dev/null; then
    echo " 连接官方 PyPI 源失败，自动切换到阿里云镜像。"
    PIP_OPTIONS="--index-url https://mirrors.aliyun.com/pypi/simple/"
else
    echo " 网络连接正常，使用官方源。"
fi
echo ""

# 步骤 5: 安装所有依赖
echo "[5/5] 正在安装所有依赖库，请耐心等待..."
echo " 首先安装 PyTorch..."
eval $PYTORCH_CMD $PIP_OPTIONS
if [ $? -ne 0 ]; then
    echo " 错误: PyTorch 安装失败！请检查网络或错误信息。"
    exit 1
fi

echo ""
echo " 正在安装其余依赖..."
pip install -r requirements.txt $PIP_OPTIONS
if [ $? -ne 0 ]; then
    echo " 错误: 其余依赖安装失败！请检查网络或错误信息。"
    exit 1
fi

echo ""
echo " ==============================================="
echo " 所有依赖已成功安装！"
echo ""
echo " 现在，你可以运行 \"./start.sh\" 来启动程序了。"
echo " ==============================================="
echo ""
exit 0