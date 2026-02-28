# Simple Subtitle Maker
关于明明实现不难但找不到三合一的软件不得不自己做这档子事。/n
感谢gemini对本项目的倾情贡献
它并非一个全功能的字幕软件，而是一个专注于“对轴-微调”场景的辅助工具。


### 何时**不**应使用本工具
如果你的需求是：
*   **制作高级特效字幕**（动态、样式、定位等），更推荐使用 [**Aegisub**](https://github.com/Aegisub/Aegisub)
*   **批量翻译已有的字幕文件**，功能更全面的 [**AITranslator**](https://github.com/jxq1997216/AITranslator) 是更好的选择。

## 主要功能

*   **AI 语音转写**: 使用 Faster-Whisper 将媒体文件转为带时间轴的字幕。
*   **可视化对轴**: 通过拖拽音频波形图区域，直观地调整字幕的开始和结束时间。（狠狠的抄我最爱的aeg，怎么aeg没有whisper插件和llm插件😡）
*   **单句重生成/重翻译**: 对任意单句字幕，可独立进行重新识别或调用大语言模型进行翻译。
*   **基础编辑**: 支持字幕文本编辑、合并、拆分等基本操作。（没做插入，拆分凑合用吧）

### 系统依赖
*   **Python** (3.8 或更高版本)
*   **FFmpeg**: 
    *   **Windows**: 下载后，在程序“设置”中配置 `ffmpeg.exe` 的路径。
    *   **Linux (Debian/Ubuntu)**: 在终端运行 `sudo apt update && sudo apt install ffmpeg`。通常无需在程序内额外配置路径。
*   **VLC (用于视频播放预览)**:
    *   **Windows**: 推荐安装 [VLC Media Player](https://www.videolan.org/vlc/)。
    *   **Linux (Debian/Ubuntu)**: 必须安装核心库和开发文件，运行 `sudo apt install libvlc-dev vlc`。

## 安装与运行

本项目提供了自动化脚本，请依次执行以下步骤：
1.  **下载项目**
    通过 `git clone` 或直接下载 ZIP 包解压。
2.  **放置模型文件**
    在项目根目录下创建一个 `models` 文件夹，并将 Faster-Whisper 模型文件夹放入其中。
3.  **执行安装脚本**
    *   **Windows**: 双击运行 `install.bat`。
    *   **Linux / macOS**: 在终端中运行 `chmod +x install.sh`，然后运行 `./install.sh`。
    脚本会自动创建虚拟环境、检查 CUDA 并安装所有依赖。
4.  **启动程序**
    *   **Windows**: 双击运行 `start.bat`。
    *   **Linux / macOS**: 在终端中运行 `./start.sh`。

5.  **注意**
    自动化脚本没有经过测试，如果有问题请在issue中反馈。

### Python 库
`requirements.txt` 中已列出所有必需库，安装脚本会自动处理，但你也可以手动安装。

## 注意
1.  **首次使用前**，请务必在程序界面的“设置”中配置你的 **FFmpeg 路径**和 **OpenAI格式的 API** 信息（支持本地模型，无key留空即可）。
2.  程序的缓存文件保存在主目录下的 `whisper_cache` 文件夹内，如有需要请随意删除。
3.  本工具的视频播放功能仅用于对轴预览，不保证兼容所有编码格式。

## 许可证

本项目采用 [**GNU General Public License v3.0**](https://www.gnu.org/licenses/gpl-3.0.html) 许可证。


## 致谢

本项目依赖于以下项目：

*   [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)
*   [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
*   [FFmpeg](https://ffmpeg.org/)
*   [VideoLAN (VLC)](https://www.videolan.org/)
*   [PyQtGraph](http://www.pyqtgraph.org/)
