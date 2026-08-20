# -*- coding: utf-8 -*-
"""
路由追踪测试：调用系统 tracert/traceroute，解析逐跳结果，标记异常节点。
性能优化：
  - Windows: tracert -w 1000（默认 4000ms，超时跳 4 倍提速）
  - Linux/macOS: traceroute -w 2 -q 1（每跳只测 1 个探测包）
  - 总超时按跳数动态计算，避免不可达目标长时间等待
"""
import re

from .base_test import BaseTest, STATUS_OK, STATUS_WARN, STATUS_BAD, STATUS_SKIP
from .tcp_test import TcpProbeTest
import platform_info


class TracerouteTest(BaseTest):
    name = "路由追踪 Tracert"

    def __init__(self, host: str, max_hops: int = 30, timeout: float = 120,
                 verify_port: int = None):
        """
        verify_port: 目标端口。当 tracert 全超时/中断（疑似路径禁 ICMP）时，
        自动用 TCP 交叉验证：TCP 通 -> 跳过；TCP 不通 -> 判定不可达。
        """
        super().__init__(timeout=timeout)
        self.host = host
        self.max_hops = max_hops
        self.verify_port = verify_port

    def _do_run(self):
        os_name = platform_info.detect_os()
        if os_name == "windows":
            # -w 1000：每包超时 1s（默认 4s），超时跳耗时降为 1/4
            cmd = ["tracert", "-d", "-h", str(self.max_hops), "-w", "1000", self.host]
        else:
            # -w 2（秒） -q 1：每跳只发 1 个探测包，超时跳耗时降为 1/3
            cmd = ["traceroute", "-n", "-m", str(self.max_hops), "-w", "2", "-q", "1", self.host]

        # 动态总超时：最坏情况（全部跳超时）≈ 跳数 × 每跳耗时 + 余量
        # Windows 每跳最多 3×1s=3s；Linux/macOS 每跳 1×2s=2s
        worst = self.max_hops * 3 + 20
        proc = platform_info.run_cmd(cmd, timeout=min(self.timeout, worst),
                                     stop_event=self.stop_event)
        self._check_cancelled()
        output = platform_info.decode_bytes(proc.stdout) + platform_info.decode_bytes(proc.stderr)
        self.result.raw_text = output

        hops = self._parse(output)
        self.result.extra = hops
        if not hops or all(h.get("timeout") for h in hops):
            # 全超时/无有效输出：交叉验证区分“路径禁 ICMP”与“真不可达”
            self._judge_blocked(output)
            return

        # 统计异常跳（超时 * 或延迟 > 200ms）
        timeouts = [h for h in hops if h.get("timeout")]
        slow = [h for h in hops if not h.get("timeout") and h.get("ms", 0) > 200]
        last_ok = not hops[-1].get("timeout")  # 末跳可达 = 目标路由可达

        self.result.key_metrics = {
            "跳数": f"{len(hops)} 跳",
            "超时跳": f"{len(timeouts)} 个",
            "慢速跳": f"{len(slow)} 个",
        }
        if not last_ok:
            # 末跳不响应：多为目标禁 ICMP（tracert 探测被忽略），用 TCP 交叉验证区分
            if self.verify_port:
                tcp = TcpProbeTest(self.host, self.verify_port, timeout=10).run()
                if tcp.status == STATUS_OK:
                    self.result.status = STATUS_OK
                    self.result.message = (
                        "目标路径探测受限（末跳及中间节点不响应 ICMP），但 TCP 端口连通正常，"
                        "链路实际可达（禁 ICMP 属常见安全配置）")
                    self.result.hint = "无需处理：目标及路径设备禁 ICMP，不影响实际访问"
                    self.result.detail = (
                        f"共 {len(hops)} 跳，{len(timeouts)} 跳超时（禁 ICMP 所致），"
                        f"已通过 TCP {self.verify_port} 验证连通正常")
                    return
            self.result.status = STATUS_BAD
            self.result.message = f"路径在第 {timeouts[0]['hop'] if timeouts else '?'} 跳后中断，目标不可达，建议检查该节点后的链路"
            self.result.hint = "重点排查中断节点之后的链路（可能是防火墙拦截或线路中断），将本报告发运维"
        elif timeouts or slow:
            # 末跳可达但存在中间跳超时：多为中间路由器禁 ICMP（不响应探测），属常见现象
            self.result.status = STATUS_OK
            self.result.message = ("路径可达（末跳正常）。中间节点有 "
                                   f"{len(timeouts)} 跳不响应探测（常见：路由器禁 ICMP），不影响实际访问")
        else:
            self.result.status = STATUS_OK
            self.result.message = f"路径 {len(hops)} 跳全程正常，无异常节点"
        self.result.detail = f"共 {len(hops)} 跳到达目标，其中超时 {len(timeouts)} 跳、延迟>200ms {len(slow)} 跳"

    def _judge_blocked(self, output: str):
        """tracert 全超时：用 TCP 交叉验证区分“路径禁 ICMP”与“真不可达”"""
        self.result.raw_text = output
        self.result.key_metrics = {"跳数": "-（全超时）"}
        if self.verify_port:
            tcp = TcpProbeTest(self.host, self.verify_port, timeout=10).run()
            if tcp.status == STATUS_OK:
                self.result.status = STATUS_SKIP
                self.result.key_metrics = {
                    "跳数": "-（路径禁 ICMP）",
                    "TCP 端口": f"{self.verify_port} 可连接",
                }
                self.result.detail = (
                    f"Tracert 全部超时（网络路径可能禁 ICMP），但 TCP {self.verify_port} 端口连通正常")
                self.result.message = "路径禁 ICMP（tracert 不可用），已通过 TCP 验证连通性，自动跳过该项"
                self.result.hint = "无需处理：网络设备禁 ICMP 属常见安全配置"
                return
        self.result.status = STATUS_BAD
        self.result.detail = "路由追踪全部超时，且 TCP 端口探测也失败"
        self.result.message = "目标不可达（路由与 TCP 均失败），请检查网络连接或联系运维"
        self.result.hint = "先换网络复测；仍不通则可能是链路中断，将本报告发运维排查"

    def _parse(self, output: str) -> list:
        """解析逐跳输出为 [{hop, ip, ms, timeout}] 列表"""
        hops = []
        for line in output.splitlines():
            m = re.match(r"\s*(\d+)[\s.]+", line)
            if not m:
                continue
            hop = int(m.group(1))
            rest = line[m.end():]
            if "*" in rest.split()[0] if rest.split() else True:
                timeout = "*" in rest
                hops.append({"hop": hop, "ip": "*", "ms": 0, "timeout": True})
                continue
            nums = re.findall(r"([\d.]+)\s*ms", rest)
            ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", rest)
            ip = ip_match.group(0) if ip_match else "-"
            ms = 0.0
            if nums:
                vals = [float(n) for n in nums]
                ms = round(sum(vals) / len(vals), 1)
            timeout = not nums or any(v >= 2000 for v in (float(n) for n in nums))
            hops.append({"hop": hop, "ip": ip, "ms": ms, "timeout": timeout or not nums})
        return hops
