# -*- coding: utf-8 -*-
"""v2 历史趋势存储：按周分文件的 JSON

设计稿 5.6 特性 F：
- history/YYYY-Wxx.json 单文件 ≤ 200 条，30 天自动归档清理
- 全部本地、UTF-8、纯文本（透明可备份）
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Iterable


def get_history_dir() -> str:
    """获取历史目录（项目根下的 history/）"""
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(project_root, "history")


def _week_key(dt: datetime) -> str:
    """获取 dt 所在的年份+ISO周编号，如 '2026-W34'"""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_file(week_key: str) -> str:
    """周键 → 文件路径"""
    return os.path.join(get_history_dir(), f"{week_key}.json")


def _load_week(week_key: str) -> list:
    """加载某周的所有记录（不存在则返回空列表）"""
    path = _week_file(week_key)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_week(week_key: str, records: list) -> None:
    """保存某周的记录"""
    os.makedirs(get_history_dir(), exist_ok=True)
    path = _week_file(week_key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def append(record: dict) -> dict:
    """追加一条测试记录

    Args:
        record: {
            "time": "2026-08-20T14:23:52",  # ISO 8601
            "scenario": "game",
            "overall_score": 87,
            "overall_grade": "A",
            "targets": [
                {"id": "tx-lol", "name": "腾讯·英雄联盟", "score": 95, ...},
                ...
            ],
        }

    Returns:
        写入的完整记录（含 week_key）
    """
    dt = datetime.fromisoformat(record.get("time", datetime.now().isoformat(timespec="seconds")))
    week_key = _week_key(dt)

    full_record = {
        **record,
        "week_key": week_key,
        "timestamp": dt.timestamp(),
    }

    records = _load_week(week_key)
    records.append(full_record)
    # 单文件 ≤ 200 条
    if len(records) > 200:
        records = records[-200:]
    _save_week(week_key, records)

    # 异步清理 30 天前的旧文件（不阻塞当前写入）
    try:
        _cleanup_old_files(days=30)
    except Exception:
        pass

    return full_record


def list_recent(days: int = 30, target_id: str = None) -> list:
    """列出最近 N 天的所有记录

    Args:
        days: 最近多少天
        target_id: 仅返回包含该 target_id 的记录（None 不过滤）

    Returns:
        按 timestamp 倒序的记录列表
    """
    cutoff = datetime.now() - timedelta(days=days)
    records = []

    if not os.path.isdir(get_history_dir()):
        return []

    for fname in sorted(os.listdir(get_history_dir())):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(get_history_dir(), fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        for r in data:
            ts = r.get("timestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(ts)
            except (ValueError, OSError):
                continue
            if dt < cutoff:
                continue
            if target_id:
                targets = r.get("targets", [])
                if not any(t.get("id") == target_id for t in targets):
                    continue
            records.append(r)

    records.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
    return records


def list_by_target(target_id: str, days: int = 30) -> list:
    """列出指定目标最近 N 天的记录"""
    return list_recent(days=days, target_id=target_id)


def trend(target_id: str, days: int = 30) -> dict:
    """生成指定目标的时间序列（用于绘制折线图）

    Returns:
        {
            "target_id": str,
            "data": [
                {"time": "2026-08-20T14:23:52", "score": 95, "latency": 35, "loss": 0},
                ...
            ],
            "best": float,
            "worst": float,
            "avg": float,
        }
    """
    records = list_by_target(target_id, days)
    data = []
    scores = []
    for r in records:
        for t in r.get("targets", []):
            if t.get("id") == target_id:
                metrics = t.get("metrics", {})
                data.append({
                    "time": r.get("time"),
                    "score": t.get("score", 0),
                    "latency": metrics.get("avg_latency_ms"),
                    "loss": metrics.get("loss_pct"),
                })
                if t.get("score") is not None:
                    scores.append(t["score"])
                break

    if not scores:
        return {"target_id": target_id, "data": [], "best": 0, "worst": 0, "avg": 0}

    return {
        "target_id": target_id,
        "data": data,
        "best": max(scores),
        "worst": min(scores),
        "avg": round(sum(scores) / len(scores), 1),
    }


def clear() -> int:
    """清空所有历史记录

    Returns:
        删除的记录条数
    """
    history_dir = get_history_dir()
    if not os.path.isdir(history_dir):
        return 0
    total = 0
    for fname in os.listdir(history_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(history_dir, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            total += len(data) if isinstance(data, list) else 0
        except (json.JSONDecodeError, OSError):
            pass
        try:
            os.remove(path)
        except OSError:
            pass
    return total


def _cleanup_old_files(days: int = 30) -> int:
    """清理超过 N 天的历史文件

    Returns:
        删除的文件数
    """
    history_dir = get_history_dir()
    if not os.path.isdir(history_dir):
        return 0

    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for fname in os.listdir(history_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(history_dir, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # 文件中所有记录都超过 N 天才删除
            if isinstance(data, list) and data:
                if all(r.get("timestamp", 0) < cutoff.timestamp() for r in data):
                    os.remove(path)
                    removed += 1
            elif not data:  # 空文件
                os.remove(path)
                removed += 1
        except (json.JSONDecodeError, OSError):
            # 文件损坏，直接删除
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed


def export_all() -> list:
    """导出全部历史数据（用于"导出全部数据"功能）"""
    return list_recent(days=365 * 5)  # 5 年内全部