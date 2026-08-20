# -*- coding: utf-8 -*-
"""v2 健康度评分系统：单目标评分 + 综合评分 + 场景加权

设计稿 5.4 特性 D：
- 单目标评分（0-100）：延迟 45% + 抖动 20% + 丢包 20% + 带宽 15%
- 场景加权（game/video/office/dev/overseas/general）
- 综合评分：所有目标加权平均
- 评级：A+/A/B/C/D
"""

from __future__ import annotations

from presets.categories import get_scenario_weight, get_category


def _grade(score: float) -> tuple[str, str, str]:
    """分数转评级 + 评语 + 颜色

    Returns:
        (grade, label, color)
        grade: "A+"/"A"/"B"/"C"/"D"
        label: 用户可读的中文评语
        color: HEX 色值（用于 UI）
    """
    if score >= 90:
        return "A+", "流畅丝滑", "#00FF9F"
    if score >= 80:
        return "A", "流畅", "#00FF9F"
    if score >= 65:
        return "B", "一般", "#FFB800"
    if score >= 45:
        return "C", "略卡", "#FFB800"
    return "D", "卡顿", "#FF3D5A"


def score_single(metrics: dict, scenario: str = "general") -> dict:
    """单目标健康度评分

    Args:
        metrics: {
            "avg_latency_ms": float | None,
            "jitter_ms": float | None,
            "loss_pct": float | None,
            "bandwidth_mbps": float | None,
        }
        scenario: "game"/"video"/"office"/"dev"/"overseas"/"general"

    Returns:
        {
            "score": float,  # 0-100
            "grade": str,    # "A+"/"A"/"B"/"C"/"D"
            "label": str,    # 评语
            "color": str,    # HEX
            "components": {latency_score, jitter_score, loss_score, bandwidth_score},
            "weights": {latency, jitter, loss, bandwidth},
        }
    """
    latency = metrics.get("avg_latency_ms")
    jitter = metrics.get("jitter_ms")
    loss = metrics.get("loss_pct")
    bw = metrics.get("bandwidth_mbps")

    # 各维度归一化分（0-100）
    if latency is None:
        latency_score = 100
    else:
        latency_score = max(0.0, 100.0 - latency * 1.2)  # 100ms 归零

    if jitter is None:
        jitter_score = 100
    else:
        jitter_score = max(0.0, 100.0 - jitter * 6)

    if loss is None:
        loss_score = 100
    else:
        loss_score = max(0.0, 100.0 - loss * 12)

    if bw is None:
        bw_score = 100
    else:
        bw_score = min(100.0, bw * 2)  # 50Mbps 满分

    # 场景加权
    weights = get_scenario_weight(scenario)
    w_latency = weights["latency"]
    w_jitter = weights["jitter"]
    w_loss = weights["loss"]
    w_bw = weights["bandwidth"]

    # 综合分（保留 1 位小数）
    score = (latency_score * w_latency
             + jitter_score * w_jitter
             + loss_score * w_loss
             + bw_score * w_bw)

    grade, label, color = _grade(score)

    return {
        "score": round(score, 1),
        "grade": grade,
        "label": label,
        "color": color,
        "components": {
            "latency": round(latency_score, 1),
            "jitter": round(jitter_score, 1),
            "loss": round(loss_score, 1),
            "bandwidth": round(bw_score, 1),
        },
        "weights": weights,
    }


def score_overall(target_results: list, scenario: str = "general") -> dict:
    """综合评分（一键全测后调用）

    Args:
        target_results: [{"target": target_dict, "metrics": {...}}, ...]
        scenario: 主场景

    Returns:
        {
            "score": float,
            "grade": str,
            "label": str,
            "color": str,
            "weighted_score": float,
            "category_breakdown": {category_id: {score, count}},
            "top_targets": [...],  # 表现最好的 3 个
            "worst_targets": [...],  # 表现最差的 3 个
        }
    """
    if not target_results:
        return {
            "score": 0,
            "grade": "D",
            "label": "无数据",
            "color": "#8B95B5",
            "weighted_score": 0,
            "category_breakdown": {},
            "top_targets": [],
            "worst_targets": [],
        }

    # 给每个目标评分
    scored = []
    for item in target_results:
        target = item.get("target", {})
        metrics = item.get("metrics", {})
        # 按目标所属分类选用子场景
        target_category = target.get("category", "")
        cat = get_category(target_category)
        target_scenario = cat["scenarios"][0] if cat and cat.get("scenarios") else scenario

        result = score_single(metrics, target_scenario)
        scored.append({
            "target": target,
            "metrics": metrics,
            **result,
        })

    # 按 weight 加权平均
    total_weight = sum(s["target"].get("weight", 50) for s in scored)
    if total_weight <= 0:
        weighted_score = sum(s["score"] for s in scored) / len(scored)
    else:
        weighted_score = sum(s["score"] * s["target"].get("weight", 50) for s in scored) / total_weight

    grade, label, color = _grade(weighted_score)

    # 按分类聚合
    category_breakdown = {}
    for s in scored:
        cat_id = s["target"].get("category", "unknown")
        if cat_id not in category_breakdown:
            category_breakdown[cat_id] = {"scores": [], "count": 0}
        category_breakdown[cat_id]["scores"].append(s["score"])
        category_breakdown[cat_id]["count"] += 1
    for cat_id in category_breakdown:
        scores = category_breakdown[cat_id]["scores"]
        avg = sum(scores) / len(scores) if scores else 0
        g, l, c = _grade(avg)
        category_breakdown[cat_id] = {
            "score": round(avg, 1),
            "grade": g,
            "label": l,
            "color": c,
            "count": len(scores),
        }

    # 排序：最好的 3 / 最差的 3
    sorted_by_score = sorted(scored, key=lambda s: -s["score"])
    top_targets = sorted_by_score[:3]
    worst_targets = sorted_by_score[-3:][::-1]  # 从最差到稍好

    return {
        "score": round(weighted_score, 1),
        "grade": grade,
        "label": label,
        "color": color,
        "weighted_score": round(weighted_score, 1),
        "category_breakdown": category_breakdown,
        "top_targets": [
            {
                "id": t["target"]["id"],
                "name": t["target"]["name"],
                "score": t["score"],
                "grade": t["grade"],
                "label": t["label"],
            }
            for t in top_targets
        ],
        "worst_targets": [
            {
                "id": t["target"]["id"],
                "name": t["target"]["name"],
                "score": t["score"],
                "grade": t["grade"],
                "label": t["label"],
            }
            for t in worst_targets
        ],
    }