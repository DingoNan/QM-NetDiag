# -*- coding: utf-8 -*-
"""v2 成就系统：5 个首批成就 + 防刷约束

设计稿 5.7 特性 G：
- 首次出发：完成第 1 次测试（无防刷）
- 十测老手：累计 10 次测试（同一目标 5 分钟内重复不计）
- 深夜测网人：任意 3 天在 23:00-05:00 完成测试（每天最多计 1 次）
- 节点医生：累计 20 次海外目标测试（失败/超时同样计）
- 全网通：单次测试覆盖 5 个以上分类
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta


USER_DATA_FILE = "user_data.json"


def _get_user_data_path() -> str:
    """获取 user_data.json 路径（项目根下）"""
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(project_root, USER_DATA_FILE)


def _load_user_data() -> dict:
    """加载用户成就数据"""
    path = _get_user_data_path()
    if not os.path.exists(path):
        return {"achievements": {}, "test_log": [], "last_test_times": {}}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"achievements": {}, "test_log": [], "last_test_times": {}}


def _save_user_data(data: dict) -> None:
    """保存用户成就数据"""
    path = _get_user_data_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# 成就定义
# ============================================================================
ACHIEVEMENTS = [
    {
        "id": "first_step",
        "name": "首次出发",
        "description": "完成第 1 次网络测试",
        "icon": "🚀",
        "color": "#00E5FF",
        "check": "_check_first_step",
    },
    {
        "id": "veteran",
        "name": "十测老手",
        "description": "累计完成 10 次测试",
        "icon": "🎖",
        "color": "#8B5CF6",
        "check": "_check_veteran",
    },
    {
        "id": "night_tester",
        "name": "深夜测网人",
        "description": "任意 3 天在 23:00-05:00 完成测试",
        "icon": "🌙",
        "color": "#FF3D9A",
        "check": "_check_night_tester",
    },
    {
        "id": "node_doctor",
        "name": "节点医生",
        "description": "累计 20 次海外目标测试",
        "icon": "🌐",
        "color": "#FFB800",
        "check": "_check_node_doctor",
    },
    {
        "id": "all_network",
        "name": "全网通",
        "description": "单次测试覆盖 5 个以上分类",
        "icon": "🎯",
        "color": "#00FF9F",
        "check": "_check_all_network",
    },
]


# ============================================================================
# 防刷与计数辅助
# ============================================================================
def _is_target_recent(target_id: str, last_test_times: dict, cooldown_minutes: int = 5) -> bool:
    """判断目标是否在 cooldown 内（防止 5 分钟内重复计数）"""
    last = last_test_times.get(target_id)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt) < timedelta(minutes=cooldown_minutes)
    except (ValueError, TypeError):
        return False


def _valid_test_record(record: dict, last_test_times: dict) -> bool:
    """判断该测试记录是否计入成就（同目标 cooldown）"""
    targets = record.get("targets", [])
    # 至少有一个目标不在 cooldown 内
    for t in targets:
        tid = t.get("id")
        if tid and not _is_target_recent(tid, last_test_times):
            return True
    return False


# ============================================================================
# 成就检查函数
# ============================================================================
def _check_first_step(data: dict, record: dict) -> bool:
    return len(data.get("test_log", [])) >= 1


def _check_veteran(data: dict, record: dict) -> bool:
    return len(data.get("test_log", [])) >= 10


def _check_night_tester(data: dict, record: dict) -> bool:
    night_days = set()
    for entry in data.get("test_log", []):
        try:
            dt = datetime.fromisoformat(entry.get("time", ""))
            hour = dt.hour
            if hour >= 23 or hour < 5:
                night_days.add(dt.date().isoformat())
        except (ValueError, TypeError):
            pass
    return len(night_days) >= 3


def _check_node_doctor(data: dict, record: dict) -> bool:
    overseas_count = sum(
        1 for entry in data.get("test_log", [])
        if any(t.get("category") == "overseas" for t in entry.get("targets", []))
    )
    return overseas_count >= 20


def _check_all_network(data: dict, record: dict) -> bool:
    categories = set()
    for t in record.get("targets", []):
        cat = t.get("category")
        if cat:
            categories.add(cat)
    return len(categories) >= 5


# ============================================================================
# 主流程
# ============================================================================
def record_test(record: dict) -> list:
    """记录一次测试，返回本次新解锁的成就列表

    Args:
        record: {
            "time": "2026-08-20T14:23:52",
            "targets": [{"id": "tx-lol", "category": "game", "score": 95, ...}, ...],
        }

    Returns:
        新解锁成就的 id 列表（空列表表示无新成就）
    """
    data = _load_user_data()
    last_test_times = data.get("last_test_times", {})

    # 防刷：检查是否有目标不在 cooldown 内
    if _valid_test_record(record, last_test_times):
        data["test_log"].append({
            "time": record.get("time", datetime.now().isoformat()),
            "targets": [
                {"id": t.get("id"), "category": t.get("category")}
                for t in record.get("targets", [])
            ],
        })
        # 限制日志大小（保留最近 200 条）
        if len(data["test_log"]) > 200:
            data["test_log"] = data["test_log"][-200:]

    # 更新每个目标的最后测试时间
    for t in record.get("targets", []):
        tid = t.get("id")
        if tid:
            last_test_times[tid] = record.get("time", datetime.now().isoformat())

    data["last_test_times"] = last_test_times

    # 检查成就解锁
    achievements = data.setdefault("achievements", {})
    newly_unlocked = []

    for ach in ACHIEVEMENTS:
        ach_id = ach["id"]
        if achievements.get(ach_id, {}).get("unlocked"):
            continue  # 已解锁
        # 调用对应检查器
        check_fn = globals().get(ach["check"])
        if check_fn and check_fn(data, record):
            achievements[ach_id] = {
                "unlocked": True,
                "unlocked_at": datetime.now().isoformat(),
            }
            newly_unlocked.append(ach_id)

    data["achievements"] = achievements
    _save_user_data(data)
    return newly_unlocked


def list_unlocked() -> list:
    """返回用户已解锁的成就列表（完整信息）"""
    data = _load_user_data()
    achievements = data.get("achievements", {})
    result = []
    for ach in ACHIEVEMENTS:
        ach_id = ach["id"]
        unlocked = achievements.get(ach_id, {}).get("unlocked", False)
        result.append({
            **ach,
            "unlocked": unlocked,
            "unlocked_at": achievements.get(ach_id, {}).get("unlocked_at"),
        })
    return result


def clear() -> int:
    """清空所有成就数据"""
    path = _get_user_data_path()
    if not os.path.exists(path):
        return 0
    try:
        os.remove(path)
        return 1
    except OSError:
        return 0