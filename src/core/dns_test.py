# -*- coding: utf-8 -*-
"""
DNS 解析测试：解析一体化系统域名，验证 DNS 是否正常。
"""
import socket
import threading
import time

from .base_test import BaseTest, STATUS_OK, STATUS_WARN, STATUS_BAD, STATUS_SKIP


class DnsResolveTest(BaseTest):
    name = "DNS 解析测试"

    def __init__(self, hostname: str = "", timeout: float = 10):
        super().__init__(timeout=timeout)
        self.hostname = (hostname or "").strip()

    def _do_run(self):
        if not self.hostname:
            self.result.status = STATUS_SKIP
            self.result.message = "未配置一体化系统域名，已跳过（可在设置中填写）"
            return

        # getaddrinfo 无超时参数，用线程 + join 限制总耗时，避免卡住整个检测流程
        holder = {}

        def _resolve():
            try:
                holder["infos"] = socket.getaddrinfo(self.hostname, None, socket.AF_INET)
            except socket.gaierror:
                holder["infos"] = None

        t = threading.Thread(target=_resolve, daemon=True)
        start = time.time()
        t.start()
        t.join(timeout=self.timeout)
        if t.is_alive():
            self.result.status = STATUS_BAD
            self.result.detail = f"域名 {self.hostname} 解析超时（>{self.timeout}s）"
            self.result.message = "DNS 解析超时，域名服务器无响应"
            self.result.hint = "检查本机 DNS 配置，可尝试改用公共 DNS（223.5.5.5 / 114.114.114.114）后重测"
            self.result.key_metrics = {"域名": self.hostname, "结果": "解析超时"}
            return

        cost_ms = round((time.time() - start) * 1000, 1)
        infos = holder.get("infos")
        if infos is None:
            self.result.status = STATUS_BAD
            self.result.detail = f"域名 {self.hostname} 解析失败"
            self.result.message = "DNS 解析失败，一体化系统域名无法解析"
            self.result.hint = "检查本机 DNS 配置，可尝试改用公共 DNS（223.5.5.5 / 114.114.114.114）后重测"
            self.result.key_metrics = {"域名": self.hostname, "结果": "解析失败"}
            return

        ips = sorted({info[4][0] for info in infos})
        self.result.status = STATUS_OK
        self.result.key_metrics = {
            "域名": self.hostname,
            "结果": f"解析到 {len(ips)} 个地址",
            "耗时": f"{cost_ms} ms",
        }
        self.result.detail = f"解析 {self.hostname} -> {', '.join(ips)}，耗时 {cost_ms} ms"
        self.result.message = "DNS 解析正常"
