@echo off
setlocal enabledelayedexpansion

:: =================================================================
:: Whisper GUI Subtitle Tool - 自动安装脚本
:: =================================================================

echo.
echo  欢迎使用 Whisper GUI Subtitle Tool 安装程序
echo  ================================================
echo.
echo  此脚本将自动完成以下操作:
echo  1. 检查 Python 环境
echo  2. 创建独立的虚拟环境 (venv)
echo  3. 检查 NVIDIA CUDA 并确定 PyTorch 版本
echo  4. 自动切换镜像源 (如果需要)
echo  5. 安装所有必需的 Python 依赖库
echo.

pause

:: 步骤 1: 检查 Python 是否已安装
echo [1/5] 正在检查 Python 环境...
python --version >nul 2>nul
if !errorlevel! neq 0 (
    echo.
    echo  错误: 未找到 Python!
    echo  请先从 python.org 安装 Python 3.8 或更高版本，并确保将其添加至系统 PATH。
    echo.
    pause
    exit /b 1
)
echo  Python 环境正常。
echo.

:: 步骤 2: 创建虚拟环境
echo [2/5] 正在准备虚拟环境...
if not exist venv (
    echo  正在创建新的虚拟环境 (venv)...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo  错误: 创建虚拟环境失败。
        pause
        exit /b 1
    )
) else (
    echo  已找到现有的虚拟环境 (venv)。
)
echo  虚拟环境准备就绪。
echo.

:: 激活虚拟环境以进行后续操作
call venv\Scripts\activate.bat

:: 步骤 3: 检查 CUDA 并确定 PyTorch 版本
echo [3/5] 正在检测 NVIDIA CUDA 并配置 PyTorch...
set PYTORCH_CMD=pip install torch
where nvidia-smi >nul 2>nul
if !errorlevel! equ 0 (
    echo  检测到 NVIDIA 显卡驱动。正在查询 CUDA 版本...
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=cuda_version --format=csv,noheader') do set CUDA_VERSION=%%i
    
    echo  检测到的 CUDA 版本: !CUDA_VERSION!
    
    for /f "tokens=1 delims=." %%v in ("!CUDA_VERSION!") do set CUDA_MAJOR=%%v

    if "!CUDA_MAJOR!" equ "12" (
        echo  配置为安装 CUDA 12.1 对应的 PyTorch。
        set PYTORCH_CMD=pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    ) else if "!CUDA_MAJOR!" equ "11" (
        echo  配置为安装 CUDA 11.8 对应的 PyTorch。
        set PYTORCH_CMD=pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    ) else (
        echo  警告: 未知的 CUDA 版本 (!CUDA_VERSION!)，将安装 CPU 版本的 PyTorch。
    )
) else (
    echo  未检测到 NVIDIA 显卡或 nvidia-smi。将安装 CPU 版本的 PyTorch。
)
echo.

:: 步骤 4: 检查网络并选择镜像源
echo [4/5] 正在测试网络连接以选择最佳下载源...
set PIP_OPTIONS=
ping -n 1 pypi.org >nul
if !errorlevel! neq 0 (
    echo  连接官方 PyPI 源失败，自动切换到阿里云镜像。
    set PIP_OPTIONS=--index-url https://mirrors.aliyun.com/pypi/simple/
) else (
    echo  网络连接正常，使用官方源。
)
echo.

:: 步骤 5: 安装所有依赖
echo [5/5] 正在安装所有依赖库，请耐心等待...
echo  首先安装 PyTorch...
!PYTORCH_CMD! !PIP_OPTIONS!
if !errorlevel! neq 0 (
    echo  错误: PyTorch 安装失败！请检查网络或错误信息。
    pause
    exit /b 1
)

echo.
echo  正在安装其余依赖...
pip install -r requirements.txt !PIP_OPTIONS!
if !errorlevel! neq 0 (
    echo  错误: 其余依赖安装失败！请检查网络或错误信息。
    pause
    exit /b 1
)

echo.
echo  ==============================================
echo  所有依赖已成功安装！
echo.
echo  现在，你可以双击 "start.bat" 来启动程序了。
echo  ==============================================
echo.
pause
exit /b 0