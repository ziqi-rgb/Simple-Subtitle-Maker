# config.py
# 存放所有用户配置和全局常量，并负责从 settings.json 加载/保存

import os
import json
from pathlib import Path

# --- 默认翻译提示词 ---
DEFAULT_STANDARD_TRANSLATION_PROMPT = """Translate the following subtitle text into Simplified Chinese.
Maintain the original meaning and tone.
Only output the translated text, with no additional explanations, context, or quotation marks.

Text: "{text}"
"""

DEFAULT_CONTEXT_TRANSLATION_PROMPT = """You are a subtitle translator. Based on the previous context, translate the current subtitle text into Simplified Chinese.
Maintain the original meaning and tone.
Only output the translated text for the "current text", with no additional explanations, context, or quotation marks.

Context:
---
{context}
---
Current text: "{text}"
"""

# --- 默认设置 ---
DEFAULT_SETTINGS = {
    # 路径设置
    "vlc_path": r"C:\Program Files\VideoLAN\VLC",
    "ffmpeg_path": r"H:\TOOLS\fffgui\ffmpeg.exe",
    "models_dir": "./models",
    # Whisper 转写参数
    "beam_size": 5,
    "vad_min_silence_ms": 500,
    "language": "auto",
    "word_timestamps": False,
    "initial_prompt": "",
    # 翻译API设置
    "openai_api_base": "https://api.openai.com/v1",
    "openai_api_key": "",
    "openai_model": "gpt-3.5-turbo",
    "translation_context_lines": 3,  # 新增：上下文行数
    # 翻译提示词管理 (结构更新)
    "translation_prompts": {
        "standard": {
            "默认翻译(中)": DEFAULT_STANDARD_TRANSLATION_PROMPT,
        },
        "contextual": {
            "默认上下文翻译(中)": DEFAULT_CONTEXT_TRANSLATION_PROMPT,
        }
    },
    "active_standard_prompt_name": "默认翻译(中)",
    "active_contextual_prompt_name": "默认上下文翻译(中)"
}

SETTINGS_FILE = Path("settings.json")

def _migrate_old_settings(settings):
    """如果检测到旧版配置，将其迁移到新结构"""
    if "translation_prompts" in settings and isinstance(settings["translation_prompts"], dict):
        if not all(isinstance(v, dict) for v in settings["translation_prompts"].values()):
            print("正在迁移旧版提示词配置...")
            old_prompts = settings["translation_prompts"]
            settings["translation_prompts"] = {
                "standard": old_prompts,
                "contextual": {
                    "默认上下文翻译(中)": DEFAULT_CONTEXT_TRANSLATION_PROMPT
                }
            }
            settings["active_standard_prompt_name"] = settings.get("active_translation_prompt_name", list(old_prompts.keys())[0])
            settings["active_contextual_prompt_name"] = "默认上下文翻译(中)"
    return settings

def load_settings():
    """从 settings.json 加载设置，如果文件不存在则返回默认值"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                loaded = _migrate_old_settings(loaded) # 迁移检查
                settings = DEFAULT_SETTINGS.copy()
                # 深度合并字典
                for key, value in loaded.items():
                    if isinstance(value, dict) and key in settings and isinstance(settings[key], dict):
                        settings[key].update(value)
                    else:
                        settings[key] = value
                return settings
        except (json.JSONDecodeError, TypeError):
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings_dict):
    """将设置字典保存到 settings.json"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, indent=4, ensure_ascii=False)

SETTINGS = load_settings()

VLC_INSTALL_DIR = SETTINGS.get("vlc_path")
FFMPEG_PATH = SETTINGS.get("ffmpeg_path")
MODELS_DIR = Path(SETTINGS.get("models_dir"))
CACHE_DIR = Path("./whisper_cache")

def setup_environment():
    """初始化文件夹和环境变量"""
    if VLC_INSTALL_DIR and Path(VLC_INSTALL_DIR).exists():
        os.environ['PYTHON_VLC_MODULE_PATH'] = VLC_INSTALL_DIR
    os.environ['VLC_VERBOSE'] = '-1'; os.environ['AV_LOG_LEVEL'] = 'quiet'
    CACHE_DIR.mkdir(exist_ok=True); MODELS_DIR.mkdir(exist_ok=True)