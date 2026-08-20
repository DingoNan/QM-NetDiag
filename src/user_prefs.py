# -*- coding: utf-8 -*-
"""
v2 用户偏好存储：收藏夹 + 自定义目标 + 设置

存储在 user_prefs.json（项目根下），与 user_data.json（成就）分开
"""

from __future__ import annotations

import json
import os
from datetime import datetime

USER_PREFS_FILE = "user_prefs.json"


def _get_path() -> str:
    """获取 user_prefs.json 路径"""
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(project_root, USER_PREFS_FILE)


def _load() -> dict:
    """加载用户偏好"""
    path = _get_path()
    if not os.path.exists(path):
        return {"favorites": [], "custom_targets": [], "settings": {}}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"favorites": [], "custom_targets": [], "settings": {}}


def _save(data: dict) -> None:
    """保存用户偏好"""
    path = _get_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# 收藏夹（favorites）
# ============================================================================
def get_favorites() -> list:
    """获取收藏的目标 id 列表"""
    return _load().get("favorites", [])


def add_favorite(target_id: str) -> list:
    """添加收藏（最多 5 个）"""
    data = _load()
    favs = data.get("favorites", [])
    if target_id not in favs:
        favs.append(target_id)
        if len(favs) > 5:
            favs = favs[-5:]  # 保留最近的 5 个
        data["favorites"] = favs
        _save(data)
    return favs


def remove_favorite(target_id: str) -> list:
    """移除收藏"""
    data = _load()
    favs = data.get("favorites", [])
    if target_id in favs:
        favs.remove(target_id)
        data["favorites"] = favs
        _save(data)
    return favs


def clear_favorites() -> None:
    """清空收藏"""
    data = _load()
    data["favorites"] = []
    _save(data)


# ============================================================================
# 自定义目标（custom_targets）
# ============================================================================
def get_custom_targets() -> list:
    """获取用户自定义目标列表"""
    return _load().get("custom_targets", [])


def add_custom_target(target: dict) -> list:
    """添加自定义目标

    Args:
        target: {
            "name": "我的服务器",
            "host": "192.168.1.100",
            "port": 8080,
            "test_type": "tcp",  # ping/tcp/http
            "note": "公司测试服",
        }

    Returns:
        完整的自定义目标列表（含 id）
    """
    data = _load()
    customs = data.get("custom_targets", [])
    target.setdefault("id", f"custom-{int(datetime.now().timestamp() * 1000)}")
    target.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    target.setdefault("category", "custom")
    target["icon"] = "custom"
    target["weight"] = 50
    target["region"] = "domestic"
    target["suggested_test"] = target.get("test_type", "tcp")
    target["fallback"] = []
    target["data_updated"] = datetime.now().strftime("%Y-%m-%d")
    customs.append(target)
    data["custom_targets"] = customs
    _save(data)
    return customs


def remove_custom_target(target_id: str) -> list:
    """移除自定义目标"""
    data = _load()
    customs = [t for t in data.get("custom_targets", []) if t.get("id") != target_id]
    data["custom_targets"] = customs
    _save(data)
    return customs


def get_all_targets_with_custom() -> list:
    """获取预置 + 自定义目标的完整列表"""
    from .presets.targets import PRESET_TARGETS
    result = list(PRESET_TARGETS) + get_custom_targets()
    return result


# ============================================================================
# 设置（settings）
# ============================================================================
DEFAULT_SETTINGS = {
    "theme": "dark",                # dark / light / system
    "font_size": "standard",        # standard / large
    "default_test_count": 5,        # 一键全测默认目标数
    "test_timeout": 5,              # 单项超时（秒）
    "ping_count": 5,                # Ping 次数
    "show_custom_in_poster": False, # 海报中显示自定义目标
}


def get_settings() -> dict:
    """获取设置（合并默认值）"""
    data = _load()
    settings = dict(DEFAULT_SETTINGS)
    settings.update(data.get("settings", {}))
    return settings


def update_setting(key: str, value) -> dict:
    """更新单个设置"""
    data = _load()
    if "settings" not in data:
        data["settings"] = dict(DEFAULT_SETTINGS)
    data["settings"][key] = value
    _save(data)
    return data["settings"]


def reset_settings() -> dict:
    """重置为默认设置"""
    data = _load()
    data["settings"] = dict(DEFAULT_SETTINGS)
    _save(data)
    return data["settings"]


# ============================================================================
# 全清
# ============================================================================
def clear_all() -> int:
    """清空所有用户数据（收藏 + 自定义 + 设置）

    Returns:
        1 表示成功
    """
    path = _get_path()
    if not os.path.exists(path):
        return 0
    try:
        os.remove(path)
        return 1
    except OSError:
        return 0