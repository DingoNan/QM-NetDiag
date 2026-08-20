# -*- coding: utf-8 -*-
"""
测试基类与结果结构：所有测试项统一输出 TestResult 字典，
供界面展示与报告生成共用。
"""
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# 状态常量
STATUS_OK = "ok"          # 正常（绿）
STATUS_WARN = "warn"      # 轻微异常（黄）
STATUS_BAD = "bad"        # 异常（红）
STATUS_ERROR = "error"    # 测试执行失败（红）
STATUS_SKIP = "skip"      # 跳过（灰）
STATUS_ABORTED = "aborted"  # 用户中止（灰）


class TestCancelled(Exception):
    """测试被用户中止（一键停止）时抛出"""


@dataclass
class TestResult:
    """单个测试项的通用结果结构"""
    name: str                       # 测试项名称
    status: str = STATUS_OK         # 状态
    key_metrics: dict = field(default_factory=dict)   # 关键指标 {label: value}
    detail: str = ""                # 详细描述/原始摘要
    raw_text: str = ""              # 原始输出（用于 txt 日志）
    duration: float = 0.0           # 耗时（秒）
    message: str = ""               # 结论判定
    hint: str = ""                  # 下一步修复提示（给用户的行动建议）
    extra: Any = None               # 扩展数据（如逐跳列表、事件列表）

    def to_dict(self) -> dict:
        return asdict(self)


class BaseTest:
    """测试基类：统一执行、计时、超时处理"""

    # 子类覆盖
    name = "测试项"
    # 用户中止信号（threading.Event），由调用方注入（如 UI 一键停止）
    stop_event = None

    def __init__(self, timeout: float = 180):
        self.timeout = timeout
        self.result = TestResult(name=self.name)

    def run(self) -> TestResult:
        """执行测试，返回 TestResult。子类实现 _do_run。"""
        start = time.time()
        try:
            self._do_run()
        except TestCancelled:
            self.result.status = STATUS_ABORTED
            self.result.message = "测试已由用户中止"
        except Exception as exc:  # noqa: BLE001 - 测试必须捕获所有异常
            self.result.status = STATUS_ERROR
            self.result.message = f"测试执行异常：{exc}"
            self.result.detail = str(exc)
        self.result.duration = round(time.time() - start, 1)
        return self.result

    def _check_cancelled(self):
        """子类在系统命令返回后调用：用户已请求中止则立即抛出"""
        if self.stop_event is not None and self.stop_event.is_set():
            raise TestCancelled()

    def _do_run(self):
        raise NotImplementedError


def summarize(level: int) -> str:
    """把 0-100 的评分转成结论文案（供报告用）"""
    if level >= 90:
        return "链路基本正常"
    if level >= 70:
        return "存在轻微异常，建议持续关注"
    return "链路质量较差，建议报修排查"
