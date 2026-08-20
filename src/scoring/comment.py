# -*- coding: utf-8 -*-
"""v2 自然语言评语生成器

根据评分结果生成：
- 单目标评语（"网络状态优秀，玩游戏毫无压力"）
- 综合评语（"整体流畅，游戏场景优秀；上传偏慢建议查运营商"）
- 行动建议（"重启路由器" / "检查节点" / "联系运营商"）
"""

from __future__ import annotations


def comment_single(metrics: dict, scenario: str = "general") -> str:
    """生成单目标自然语言评语

    Args:
        metrics: {avg_latency_ms, jitter_ms, loss_pct, bandwidth_mbps}
        scenario: 场景
    """
    latency = metrics.get("avg_latency_ms") or 999
    jitter = metrics.get("jitter_ms") or 0
    loss = metrics.get("loss_pct") or 0
    bw = metrics.get("bandwidth_mbps")

    # 优先考虑丢包（最影响体感）
    if loss > 20:
        return f"严重丢包 {loss:.0f}%，网络极不稳定，建议联系运营商"
    if loss > 5:
        return f"检测到明显丢包 ({loss:.1f}%)，建议重启路由器或检查线路"

    # 海外场景的延迟宽容度更大
    is_overseas = scenario == "overseas"
    latency_threshold_low = 200 if is_overseas else 30
    latency_threshold_high = 400 if is_overseas else 100

    if latency < latency_threshold_low and loss == 0 and jitter < 5:
        return "网络状态优秀，游戏毫无压力"
    if latency < latency_threshold_high and loss == 0 and jitter < 10:
        return "网络流畅，日常使用完全够用"
    if latency < 200 and loss < 1:
        return "网络一般，部分场景可能略有卡顿"
    if is_overseas and latency > 400:
        return "延迟较高，跨国访问或运营商线路繁忙，可考虑换节点"
    if latency > 200:
        return "延迟较高，建议检查本地网络或换用有线连接"

    return "网络状态异常，建议联系运营商或切换网络"


def comment_overall(overall: dict) -> str:
    """生成综合评语（基于 score_overall 结果）"""
    score = overall.get("score", 0)
    breakdown = overall.get("category_breakdown", {})
    top = overall.get("top_targets", [])
    worst = overall.get("worst_targets", [])

    parts = []

    # 整体评语
    if score >= 90:
        parts.append("整体表现优秀")
    elif score >= 75:
        parts.append("整体流畅")
    elif score >= 60:
        parts.append("整体一般")
    elif score >= 40:
        parts.append("整体偏弱")
    else:
        parts.append("整体不佳")

    # 最佳场景
    if top:
        top_names = "、".join([t["name"] for t in top[:2]])
        parts.append(f"亮点：{top_names}")

    # 短板场景
    if worst:
        worst_names = "、".join([t["name"] for t in worst if t["score"] < 60])
        if worst_names:
            parts.append(f"短板：{worst_names}")

    # 行动建议
    if score < 40:
        parts.append("建议立即重启路由器并联系运营商")
    elif score < 60:
        parts.append("建议检查网络或换用更快的接入方式")
    else:
        parts.append("继续保持")

    return "；".join(parts) + "。"


def suggest_action(metrics: dict) -> str:
    """根据指标给出具体行动建议

    Returns:
        1-2 条简短建议（不超过 30 字）
    """
    latency = metrics.get("avg_latency_ms") or 0
    loss = metrics.get("loss_pct") or 0
    jitter = metrics.get("jitter_ms") or 0
    bw = metrics.get("bandwidth_mbps") or 0

    actions = []

    if loss > 5:
        actions.append("检查路由器或线路")
    elif loss > 1:
        actions.append("观察一段时间")

    if latency > 150 and loss < 1:
        actions.append("靠近路由器或换 5G 频段")

    if jitter > 30:
        actions.append("检查网络稳定性")

    if bw and bw < 5:
        actions.append("升级宽带套餐")

    if not actions:
        actions.append("网络良好")

    return "，".join(actions[:2])


def short_label(metrics: dict) -> str:
    """用于卡片的简短标签（4 字以内）"""
    latency = metrics.get("avg_latency_ms") or 999
    loss = metrics.get("loss_pct") or 0

    if loss > 5 or latency > 300:
        return "卡顿"
    if loss > 1 or latency > 150:
        return "略卡"
    if latency > 80:
        return "一般"
    return "流畅"