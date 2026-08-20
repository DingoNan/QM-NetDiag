# -*- coding: utf-8 -*-
"""报告生成模块包"""
from .text_report import build_text_report, build_wechat_summary
from .html_report import build_html_report, evaluate_session, save_report, locate_problem

__all__ = ["build_text_report", "build_wechat_summary", "build_html_report",
           "evaluate_session", "save_report", "locate_problem"]
