# -*- coding: utf-8 -*-
"""
长时监测模块：后台线程周期性执行 Ping + TCP 探测 + HTTP 探测（可选），
记录每轮延迟/耗时趋势，自动识别"不稳定事件"（丢包/断连/延迟突增），输出事件时间线。
专治"时断时续"类问题。
"""
import queue
import re
import threading
import time
from dataclasses import asdict, dataclass, field

from core.ping_test import PingTest
from core.tcp_test import TcpProbeTest
from core.http_probe import HttpProbeTest
from core.base_test import STATUS_OK

# 事件类型
EV_DROP = "丢包事件"
EV_DISCONNECT = "断连事件"
EV_LATENCY = "延迟突增"


@dataclass
class MonitorEvent:
    time_str: str
    type: str
    level: str          # bad / warn
    detail: str
    ts: float = 0.0


@dataclass
class MonitorSample:
    ts: float
    time_str: str
    loss_pct: float = 0.0
    avg_ms: float = 0.0        # Ping 平均延迟
    tcp_ms: float = 0.0        # TCP 建连耗时
    http_ms: float = 0.0       # HTTP 响应耗时（未配置 HTTP 时为 0）
    tcp_ok: bool = True
    reachable: bool = True     # False=断连（用于趋势图红叉）

    def to_dict(self) -> dict:
        return asdict(self)


class NetworkMonitor(threading.Thread):
    """
    host/port: 探测目标
    interval: 探测间隔（秒）
    duration: 监测总时长（秒）；None 表示持续监测
    http_url: 一体化系统地址（可选），配置后每轮追加 HTTP 探测
    progress_cb: 每轮回调 (samples, events)
    """

    def __init__(self, host: str, port: int, interval: int = 30,
                 duration: int = 600, progress_cb=None, stop_event=None,
                 http_url: str = ""):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.interval = max(5, interval)
        self.duration = duration
        self.progress_cb = progress_cb
        self.stop_event = stop_event or threading.Event()
        self.http_url = (http_url or "").strip()
        self.samples: list = []
        self.events: list = []
        self.baseline_ms: float = None  # 基线延迟（前 3 轮均值）

    def run(self):
        start_all = time.time()
        while not self.stop_event.is_set():
            sample = self._probe_once()
            self.samples.append(sample)
            self._detect_events(sample)
            if self.progress_cb:
                self.progress_cb(list(self.samples), list(self.events))
            if self.duration and time.time() - start_all >= self.duration:
                break
            self.stop_event.wait(self.interval)

    def _probe_once(self) -> MonitorSample:
        ping = PingTest(self.host, count=5, timeout=30, verify_port=self.port).run()
        tcp = TcpProbeTest(self.host, self.port, timeout=10).run()
        loss = 0.0
        avg = 0.0
        # 健壮解析：指标可能含中文说明，如 “100%（禁 ping）”，用正则提取数字
        for key, val in ping.key_metrics.items():
            if "丢包" in key:
                m = re.search(r"[\d.]+", str(val))
                loss = float(m.group(0)) if m else 0.0
            if "平均延迟" in key:
                m = re.search(r"[\d.]+", str(val))
                avg = float(m.group(0)) if m else 0.0
        tcp_ms = 0.0
        for key, val in tcp.key_metrics.items():
            if "建连" in key:
                m = re.search(r"[\d.]+", str(val))
                tcp_ms = float(m.group(0)) if m else 0.0
        # 可选 HTTP 探测（一体化系统地址已配置时，每轮追加一次）
        http_ms = 0.0
        if self.http_url:
            http = HttpProbeTest(self.http_url, timeout=8, samples=1).run()
            if http.status in ("ok", "warn", "bad"):
                m = re.search(r"[\d.]+", str(http.key_metrics.get("平均响应", "0")))
                http_ms = float(m.group(0)) if m else 0.0
        now = time.time()
        ts_str = time.strftime("%H:%M:%S", time.localtime(now))
        return MonitorSample(
            ts=now, time_str=ts_str, loss_pct=loss, avg_ms=avg,
            tcp_ms=tcp_ms, http_ms=http_ms,
            tcp_ok=(tcp.status == STATUS_OK),
            # 禁 ping（ICMP 被禁）但 TCP 通也算可达，避免误报断连
            reachable=(ping.status == STATUS_OK or tcp.status == STATUS_OK),
        )

    def _detect_events(self, s: MonitorSample):
        """基于当前样本判定事件"""
        # 基线：前 3 个可达样本
        if self.baseline_ms is None:
            ok = [x for x in self.samples if x.reachable and x.avg_ms > 0]
            if len(ok) >= 3:
                self.baseline_ms = sum(x.avg_ms for x in ok[:3]) / 3

        # 断连：ping 全丢 + tcp 失败
        if s.loss_pct >= 100 and not s.tcp_ok:
            self._add_event(s, EV_DISCONNECT, "bad",
                            f"Ping 全部超时且 TCP {self.port} 连接失败")
            return
        # 丢包：有丢包但未完全断
        if 0 < s.loss_pct < 100:
            self._add_event(s, EV_DROP, "warn" if s.loss_pct < 20 else "bad",
                            f"丢包 {s.loss_pct:.0f}%")
            return
        # 延迟突增：相对基线 3 倍以上
        if self.baseline_ms and s.avg_ms > self.baseline_ms * 3 and s.avg_ms > 100:
            self._add_event(s, EV_LATENCY, "warn",
                            f"延迟 {s.avg_ms:.0f}ms（基线 {self.baseline_ms:.0f}ms）")

    def _add_event(self, s: MonitorSample, etype: str, level: str, detail: str):
        # 同类事件 60 秒内不重复记录
        if self.events and s.ts - self.events[-1].ts < 60 and self.events[-1].type == etype:
            return
        self.events.append(MonitorEvent(
            time_str=s.time_str, type=etype, level=level, detail=detail, ts=s.ts))

    def summary(self) -> dict:
        """生成监测摘要（供报告）
        异常口径：真断连（不可达）或真丢包（0<丢包<100%）。
        禁 ping 但 TCP 通（丢包=100%）不算异常，避免误报。
        """
        total = len(self.samples)
        bad = sum(1 for x in self.samples
                  if not x.reachable or (0 < x.loss_pct < 100))
        rate = (bad / total * 100) if total else 0
        if rate == 0:
            level, verdict = "A", "链路稳定"
        elif rate < 10:
            level, verdict = "B", "基本稳定，偶发轻微波动"
        else:
            level, verdict = "C", "不稳定，存在频繁异常事件"
        return {
            "samples": total,
            "bad_ratio": round(rate, 1),
            "level": level,
            "verdict": verdict,
            "events": len(self.events),
        }
