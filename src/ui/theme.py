# -*- coding: utf-8 -*-
"""
UI 主题：统一政务蓝配色与字体，与 HTML 原型保持一致。
"""
import sys

# 配色（与 docs/prototype/index.html 的 CSS 变量一致）
PRIMARY = "#1B5E9E"          # 政务蓝
PRIMARY_DARK = "#14487A"
PRIMARY_LIGHT = "#E8F1FA"
ACCENT = "#2196F3"
ACCENT_LIGHT = "#E3F2FD"
SUCCESS = "#2E9E5B"
SUCCESS_LIGHT = "#E8F7EE"
WARNING = "#E6A23C"
WARNING_LIGHT = "#FDF3E3"
DANGER = "#D64545"
DANGER_LIGHT = "#FDECEC"
BG = "#F5F7FA"
CARD = "#FFFFFF"
TEXT = "#2B3A4A"
MUTED = "#8A97A5"
LINE = "#E6EBF0"

STATUS_COLOR = {
    "ok": SUCCESS,
    "warn": WARNING,
    "bad": DANGER,
    "error": DANGER,
    "skip": MUTED,
    "aborted": MUTED,
}
STATUS_BG = {
    "ok": SUCCESS_LIGHT,
    "warn": WARNING_LIGHT,
    "bad": DANGER_LIGHT,
    "error": DANGER_LIGHT,
    "skip": "#F0F3F6",
    "aborted": "#F0F3F6",
}
STATUS_TEXT = {"ok": "✅ 正常", "warn": "⚠️ 异常", "bad": "❌ 异常",
               "error": "❌ 失败", "skip": "⏭️ 跳过", "aborted": "⏹ 中止"}


def is_windows() -> bool:
    return sys.platform.startswith("win")


def ui_font(size: int = 10, bold: bool = False) -> tuple:
    """返回当前平台合适的中文字体"""
    if is_windows():
        return ("Microsoft YaHei", size, "bold" if bold else "normal")
    if sys.platform == "darwin":
        return ("PingFang SC", size, "bold" if bold else "normal")
    return ("WenQuanYi Micro Hei", size, "bold" if bold else "normal")
