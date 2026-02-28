@echo off
:: =================================================================
:: Dev Shell - 快速进入虚拟环境命令行
:: =================================================================
:: 功能: 打开一个新的命令提示符窗口，并自动激活本项目的 venv 环境。
:: 用途: 方便开发者进行调试、测试或管理 Python 包。
:: =================================================================

:: 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo 错误: 虚拟环境未找到!
    echo 请先运行 "install.bat" 脚本来创建环境。
    echo.
    pause
    exit /b 1
)

echo 正在打开已激活虚拟环境的开发者命令行...

:: 使用 start 命令打开一个新的命令提示符窗口
:: "Whisper Tool - Dev Console" 是新窗口的标题
:: /k 参数表示执行后面的命令，并保持窗口打开
start "Whisper Tool - Dev Console" cmd /k "venv\Scripts\activate.bat"

exit /b 0