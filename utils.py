# utils.py
# 包含项目所需的通用工具函数

import re
from datetime import timedelta

def format_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳字符串"""
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    milliseconds = delta.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds_part:02},{milliseconds:03}"

def parse_time(time_str: str) -> float:
    """将 SRT 时间戳字符串解析为秒数"""
    try:
        parts = re.split('[:,]', time_str)
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) + int(parts[3]) / 1000.0
    except (ValueError, IndexError):
        return 0.0