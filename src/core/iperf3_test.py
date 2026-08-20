# -*- coding: utf-8 -*-
"""
iperf3 带宽测试：调用内置 iperf3 二进制（-J JSON 输出），解析带宽与重传率。
工具路径策略：
  源码运行 -> <项目根>/tools/<平台>/iperf3(.exe)
  打包运行 -> <exe目录>/tools/<平台>/iperf3(.exe)
"""
import json
import os
import sys

from .base_test import BaseTest, STATUS_OK, STATUS_WARN, STATUS_BAD, STATUS_ERROR
import platform_info


def _tools_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_iperf3() -> str:
    """定位当前平台对应的 iperf3 可执行文件；找不到返回 None"""
    os_name = platform_info.detect_os()
    arch = platform_info.detect_arch()
    if os_name == "windows":
        sub = "win64" if arch in ("x86_64", "x64") else "win32"
        name = "iperf3.exe"
    elif os_name == "linux":
        sub = "kylin_x64" if arch in ("x86_64", "x64") else "kylin_arm64" if arch == "arm64" else None
        name = "iperf3"
    elif os_name == "macos":
        sub = "macos_arm64" if arch == "arm64" else "macos_x64"
        name = "iperf3"
    else:
        return None
    if sub is None:
        return None
    path = os.path.join(_tools_root(), "tools", sub, name)
    return path if os.path.isfile(path) else None


def bandwidth_level(mbps: float) -> str:
    """带宽通俗分级说明（自动评估，无需参考值）"""
    if mbps >= 100:
        return "高速（百兆级）：可流畅支撑视频会议/大文件传输"
    if mbps >= 50:
        return "较快（50M 级）：日常办公流畅"
    if mbps >= 20:
        return "普通办公水平：日常业务基本流畅，多人并发可能变慢"
    if mbps >= 10:
        return "偏慢（10M 级）：适合单机轻量办公，大文件/视频会议会卡顿"
    if mbps >= 5:
        return "很慢（5M 级）：仅适合简单页面浏览"
    return "极慢：仅支持基础文本业务"


class Iperf3Test(BaseTest):
    """
    mode: "single" 单流 | "parallel" 并行多流 | "reverse" 反向
    """
    name = "iperf3 带宽测试"

    def __init__(self, host: str, port: int, duration: int = 30,
                 streams: int = 8, mode: str = "single",
                 reference_mbps: int = 50, timeout: float = 180,
                 src_ip: str = ""):
        super().__init__(timeout=timeout)
        self.host = host
        self.port = port
        self.duration = max(1, duration)
        self.streams = max(1, streams)
        self.mode = mode
        self.reference_mbps = reference_mbps
        self.src_ip = (src_ip or "").strip()

    def _do_run(self):
        exe = find_iperf3()
        if exe is None:
            self.result.status = STATUS_ERROR
            self.result.message = "未找到内置 iperf3 工具，请确认 tools/ 目录完整"
            return

        cmd = [exe, "-c", self.host, "-p", str(self.port),
               "-t", str(self.duration), "-J"]
        if self.mode == "parallel":
            cmd += ["-P", str(self.streams)]
        elif self.mode == "reverse":
            cmd += ["-R"]
        if self.src_ip:
            cmd += ["-B", self.src_ip]

        proc = platform_info.run_cmd(cmd, timeout=self.timeout,
                                     cwd=os.path.dirname(exe), record_pid=True,
                                     stop_event=self.stop_event)
        self._check_cancelled()
        raw = platform_info.decode_bytes(proc.stdout)
        if proc.returncode != 0:
            err = platform_info.decode_bytes(proc.stderr) or raw
            self.result.status = STATUS_BAD
            self.result.detail = err[:500]
            self.result.message = ("iperf3 测试失败：目标服务端未启动或端口不通。"
                                   "请确认服务器已运行 iperf3 -s，或检查 NAT 映射")
            return

        data = self._parse_json(raw)
        self._fill_result(data, raw)

    def _parse_json(self, raw: str) -> dict:
        """从 -J 输出中提取 JSON 部分（iperf3 可能输出多余警告行）"""
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return {}
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return {}

    def _fill_result(self, data: dict, raw: str):
        self.result.raw_text = raw
        if not data:
            self.result.status = STATUS_ERROR
            self.result.message = "iperf3 输出解析失败"
            return

        sender = data.get("end", {}).get("sum_sent", {})
        receiver = data.get("end", {}).get("sum_received", {})
        send_mbps = float(sender.get("bits_per_second", 0)) / 1e6
        recv_mbps = float(receiver.get("bits_per_second", 0)) / 1e6
        retr = int(sender.get("retransmits", 0) or 0)
        total_bytes = int(sender.get("bytes", 0) or 0)

        # 重传率估算：重传包数 / 总包数
        seg_count = int(sender.get("packets", 0) or 0)
        retr_rate = (retr / seg_count * 100) if seg_count else 0.0

        is_reverse = self.mode == "reverse"
        main_bw = recv_mbps if is_reverse else send_mbps
        direction = "下行(反向)" if is_reverse else ("上行" if self.mode == "single" else "上行并行")

        label_map = {
            "single": "单流上行",
            "parallel": f"{self.streams} 流并行",
            "reverse": "反向（下行）",
        }
        self.result.name = f"iperf3 带宽测试 · {label_map.get(self.mode, self.mode)}"
        level = bandwidth_level(main_bw)
        level_short = level.split("：")[0]

        self.result.key_metrics = {
            "带宽": f"{main_bw:.1f} Mbps",
            "带宽水平": level_short,
            "重传": f"{retr} 个",
            "重传率": f"{retr_rate:.2f}%",
        }
        if self.reference_mbps and self.reference_mbps > 0:
            ref_note = f"（参考基线 {self.reference_mbps} Mbps）"
        else:
            ref_note = f"（{level_short}）"
        self.result.detail = (
            f"{direction}带宽 {main_bw:.1f} Mbps{ref_note}，"
            f"共传输 {total_bytes / 1048576:.1f} MB，重传 {retr} 包（{retr_rate:.2f}%）"
        )

        # 判定：重传率反映链路质量；参考值可选（留空则只做质量判定）
        if retr_rate > 5:
            self.result.status = STATUS_BAD
            self.result.message = "重传率过高，链路质量差，建议报修"
            self.result.hint = "重传过高说明链路不稳定（丢包），建议换网络复测后报修运营商"
        elif retr_rate > 2:
            self.result.status = STATUS_WARN
            self.result.message = f"重传率 {retr_rate:.2f}% 略高，链路质量一般，建议观察"
            self.result.hint = "可开启长期监测观察趋势；持续升高再报修"
        elif self.reference_mbps and self.reference_mbps > 0 and main_bw < self.reference_mbps * 0.3:
            self.result.status = STATUS_BAD
            self.result.message = f"带宽低于参考值（{main_bw:.1f} vs {self.reference_mbps} Mbps）"
            self.result.hint = "核实线路实际带宽；确实低于预期则联系运营商排查限速"
        elif self.reference_mbps and self.reference_mbps > 0 and main_bw < self.reference_mbps * 0.7:
            self.result.status = STATUS_WARN
            self.result.message = f"带宽略低于参考值（{main_bw:.1f} vs {self.reference_mbps} Mbps）"
            self.result.hint = "建议核对运营商套餐实际带宽"
        else:
            self.result.status = STATUS_OK
            self.result.message = f"链路质量正常；带宽水平：{level_short}（{main_bw:.1f} Mbps）"
            self.result.hint = f"当前带宽{level_short}；若业务卡顿，建议评估是否需升级线路带宽"
