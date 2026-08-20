# -*- coding: utf-8 -*-
"""
v2 预置网站分类与场景定义。

设计原则：
- 分类按"用户场景"组织，而不是按"行业"组织（游戏玩家/视频博主等）
- 每个分类有独立图标键（避免依赖 emoji 字体）
- 场景加权用于评分（5.4 特性 D）
"""

# 分类元数据：图标、显示名、排序权重
CATEGORIES = [
    {
        "id": "game",
        "name": "游戏",
        "icon": "game",
        "color": "#FF3D9A",
        "weight": 90,
        "scenarios": ["game"],
    },
    {
        "id": "video",
        "name": "视频",
        "icon": "video",
        "color": "#8B5CF6",
        "weight": 85,
        "scenarios": ["video"],
    },
    {
        "id": "chat",
        "name": "通讯",
        "icon": "chat",
        "color": "#00E5FF",
        "weight": 80,
        "scenarios": ["office"],
    },
    {
        "id": "dev",
        "name": "开发",
        "icon": "dev",
        "color": "#00FF9F",
        "weight": 70,
        "scenarios": ["dev"],
    },
    {
        "id": "social",
        "name": "社交",
        "icon": "social",
        "color": "#FFB800",
        "weight": 60,
        "scenarios": ["office"],
    },
    {
        "id": "shopping",
        "name": "购物",
        "icon": "shopping",
        "color": "#FF9F43",
        "weight": 55,
        "scenarios": ["office"],
    },
    {
        "id": "knowledge",
        "name": "知识",
        "icon": "knowledge",
        "color": "#5B8DEF",
        "weight": 50,
        "scenarios": ["office"],
    },
    {
        "id": "overseas",
        "name": "海外",
        "icon": "overseas",
        "color": "#FF3D5A",
        "weight": 75,
        "scenarios": ["overseas"],
    },
]

# 场景加权（5.4 特性 D）
# 延迟 / 抖动 / 丢包 / 带宽 权重
SCENARIO_WEIGHTS = {
    "game":     {"latency": 0.55, "jitter": 0.25, "loss": 0.20, "bandwidth": 0.00},
    "video":    {"latency": 0.10, "jitter": 0.05, "loss": 0.10, "bandwidth": 0.75},
    "office":   {"latency": 0.35, "jitter": 0.25, "loss": 0.25, "bandwidth": 0.15},
    "dev":      {"latency": 0.40, "jitter": 0.20, "loss": 0.20, "bandwidth": 0.20},
    "overseas": {"latency": 0.50, "jitter": 0.25, "loss": 0.25, "bandwidth": 0.00},
    "general":  {"latency": 0.45, "jitter": 0.20, "loss": 0.20, "bandwidth": 0.15},
}


def get_category(category_id: str) -> dict | None:
    """按 ID 获取分类"""
    for c in CATEGORIES:
        if c["id"] == category_id:
            return c
    return None


def get_scenario_weight(scenario: str) -> dict:
    """获取场景权重，默认 general"""
    return SCENARIO_WEIGHTS.get(scenario, SCENARIO_WEIGHTS["general"])