# -*- coding: utf-8 -*-
"""
Ping 连通性测试：调用系统 ping 命令并解析统计结果。
Windows: ping -n <count> -w <timeout> <host>
Linux/macOS: ping -c <count> -W <timeout> <host>
"""
import re
import sys

from .base_test import (BaseTest, TestResult, STATUS_OK, STATUS_WARN,
                        STATUS_BAD, STATUS_ERROR, STATUS_SKIP)
from .tcp_test import TcpProbeTest
import platform_info


class PingTest(BaseTest):
    name = "Ping 连通性测试"

    def __init__(self, host: str, count: int = 50, timeout: float = 120,
                 verify_port: int = None, src_ip: str = ""):
        """
        verify_port: 目标端口（如 30014）。当 ping 全部超时（疑似服务器禁 ping）时，
        自动用 TCP 探测交叉验证：TCP 通 -> 判定“禁 ping”并跳过；
        TCP 不通 -> 判定“目标不可达”。
        src_ip: 指定源 IP（多网卡时选择测试网卡）。
        """
        super().__init__(timeout=timeout)
        self.host = host
        self.count = max(1, min(count, 1000))
        self.verify_port = verify_port
        self.src_ip = (src_ip or "").strip()

    def _do_run(self):
        os_name = platform_info.detect_os()
        # 预检：少量包快速判断可达性，避免大数量全超时长时间等待
        probe_output = self._run_ping(os_name, count=4, w=2000, timeout=20)
        probe_stats = self._parse(probe_output, os_name)
        if probe_stats["loss_pct"] >= 100:
            # 多次请求超时：进入交叉验证，判定后结束（不再发剩余包）
            self._judge_unreachable(probe_output)
            return

        # 预检有响应，执行完整 ping
        output = self._run_ping(os_name, count=self.count, w=3000,
                                timeout=min(self.timeout, self.count * 3 + 15))
        self.result.raw_text = output
        stats = self._parse(output, os_name)
        self._fill_stats(stats)
        self._judge_loss(stats, os_name, output)

    def _run_ping(self, os_name: str, count: int, w: int, timeout: float) -> str:
        if os_name == "windows":
            cmd = ["ping", "-n", str(count), "-w", str(w)]
            if self.src_ip:
                cmd += ["-S", self.src_ip]
            cmd.append(self.host)
        else:
            # macOS 的 -W 单位是毫秒，Linux 是秒；统一用毫秒值在 mac 上可用
            cmd = ["ping", "-c", str(count), "-W", str(w)]
            if self.src_ip:
                cmd += ["-I", self.src_ip]
            cmd.append(self.host)
        proc = platform_info.run_cmd(cmd, timeout=timeout, stop_event=self.stop_event)
        self._check_cancelled()
        return platform_info.decode_bytes(proc.stdout) + platform_info.decode_bytes(proc.stderr)

    def _fill_stats(self, stats: dict):
        self.result.key_metrics = {
            "发送": f"{stats['sent']} 包",
            "丢包": f"{stats['loss_pct']}%",
            "平均延迟": f"{stats['avg_ms']} ms",
        }
        self.result.detail = (
            f"发送 {stats['sent']} 包，接收 {stats['received']} 包，丢包 {stats['loss_pct']}%；"
            f"延迟 min {stats['min_ms']}ms / avg {stats['avg_ms']}ms / max {stats['max_ms']}ms"
        )

    def _judge_unreachable(self, output: str):
        """ping 全部超时：用 TCP 交叉验证区分“禁 ping”与“真不可达”"""
        self.result.raw_text = output
        self.result.key_metrics = {"丢包": "100%"}
        if self.verify_port:
            tcp = TcpProbeTest(self.host, self.verify_port, timeout=10).run()
            if tcp.status == STATUS_OK:
                self.result.status = STATUS_SKIP
                self.result.key_metrics = {
                    "丢包": "100%（禁 ping）",
                    "TCP 端口": f"{self.verify_port} 可连接",
                }
                self.result.detail = (
                    f"Ping 全部超时（服务器可能禁 ping），但 TCP {self.verify_port} 端口连通正常")
                self.result.message = "服务器禁 ping（ICMP 被禁），已通过 TCP 验证连通性，自动跳过该项"
                self.result.hint = "无需处理：服务器禁 ping 属常见配置，不影响正常访问"
                return
        self.result.status = STATUS_BAD
        self.result.detail = "Ping 多次请求超时，且 TCP 端口探测也失败"
        self.result.message = "目标不可达（ping 与 TCP 均失败），请检查网络连接或联系运维"
        self.result.hint = "先检查网线/WiFi，换网络复测一次；仍不通则可能是链路中断，将本报告发运维"

    def _judge_loss(self, stats: dict, os_name: str, output: str):
        loss = stats["loss_pct"]
        if loss >= 100:
            # 预检通过但完整 ping 全丢（罕见），同样交叉验证
            self._judge_unreachable(output)
            return
        if loss >= 5:
            self.result.status = STATUS_BAD
            self.result.message = f"丢包率 {loss}% 过高，链路存在明显质量问题，建议报修"
            self.result.hint = "丢包严重时先换网络复测（手机热点对比）；仍高则报修运营商线路"
        elif loss > 0:
            self.result.status = STATUS_WARN
            self.result.message = f"存在 {loss}% 丢包，链路质量一般，建议持续观察"
            self.result.hint = "可开启长期监测观察是否频繁丢包，确认频率后再报修"
        else:
            self.result.status = STATUS_OK
            self.result.message = "无丢包，连通性正常"

    def _parse(self, output: str, os_name: str) -> dict:
        stats = {"sent": 0, "received": 0, "loss_pct": 100.0,
                 "min_ms": 0, "avg_ms": 0, "max_ms": 0}
        # 丢包率：兼容中英文（中文输出为“丢失”）
        m = re.search(r"[（(]?\s*(\d+(?:\.\d+)?)%\s*[）)]?\s*(?:loss|丢失|丢包)", output, re.IGNORECASE)
        if m:
            stats["loss_pct"] = float(m.group(1))
        # 收发统计：兼容 "3 packets transmitted, 3 received" / “已发送 = 3，已接收 = 3”
        m = re.search(r"(\d+)\s*(?:packets? transmitted|已发送)\D*(\d+)\s*(?:received|已接收)", output, re.IGNORECASE)
        if m:
            stats["sent"], stats["received"] = int(m.group(1)), int(m.group(2))
        # 延迟统计-中文：“最短 = 0ms，最长 = 0ms，平均 = 0ms”
        m = re.search(r"最短\s*=\s*([\d.]+)\s*ms\D*最长\s*=\s*([\d.]+)\s*ms\D*平均\s*=\s*([\d.]+)\s*ms", output)
        if m:
            stats["min_ms"], stats["max_ms"], stats["avg_ms"] = (round(float(x), 1) for x in m.groups())
        else:
            # 延迟统计-英文："round-trip min/avg/max/mdev = 8.1/12.3/18.4/2.1 ms"
            m = re.search(r"(?:rtt|round-trip)\D+=\s*([\d.]+)/([\d.]+)/([\d.]+)", output, re.IGNORECASE)
            if m:
                stats["min_ms"], stats["avg_ms"], stats["max_ms"] = (round(float(x), 1) for x in m.groups())
        if stats["sent"] == 0:
            stats["sent"] = self.count
            stats["received"] = round(stats["sent"] * (100 - stats["loss_pct"]) / 100)
        return stats
