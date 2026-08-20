# -*- coding: utf-8 -*-
"""v2 预置网站库：100+ 常用网站，覆盖 8 大分类"""

from .targets import PRESET_TARGETS, get_targets, get_target, filter_by_category
from .categories import CATEGORIES, SCENARIO_WEIGHTS, get_category, get_scenario_weight

__all__ = [
    "PRESET_TARGETS",
    "CATEGORIES",
    "SCENARIO_WEIGHTS",
    "get_targets",
    "get_target",
    "filter_by_category",
    "get_category",
    "get_scenario_weight",
]