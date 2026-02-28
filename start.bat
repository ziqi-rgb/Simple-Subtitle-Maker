@echo off
:: =================================================================
:: Whisper GUI Subtitle Tool - 启动脚本
:: =================================================================

:: 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo 错误: 未找到虚拟环境!
    echo 请先双击运行 "install.bat" 来完成安装。
    pause
    exit /b 1
)

:: 激活虚拟环境
call "venv\Scripts\activate.bat"

:: 启动主程序
echo 正在启动 Whisper GUI Subtitle Tool...
python main.py

exit /b 0