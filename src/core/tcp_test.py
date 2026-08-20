# -*- coding: utf-8 -*-
"""
TCP 端口探测：用原生 socket 测试目标端口是否可建立连接，并统计建连耗时。
纯 Python 实现，无需系统命令，三平台一致。
"""
import socket
import time

from .base_test import BaseTest, STATUS_OK, STATUS_BAD


class TcpProbeTest(BaseTest):
    name = "TCP 端口探测"

    def __init__(self, host: str, port: int, timeout: float = 20, src_ip: str = ""):
        super().__init__(timeout=timeout)
        self.host = host
        self.port = port
        self.src_ip = (src_ip or "").strip()

    def _do_run(self):
        connect_ms = None
        err = None
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        # 指定源 IP（多网卡时选择测试网卡）
        if self.src_ip:
            try:
                sock.bind((self.src_ip, 0))
            except OSError:
                pass
        start = time.time()
        try:
            sock.connect((self.host, self.port))
            connect_ms = round((time.time() - start) * 1000, 1)
        except OSError as exc:
            err = exc
        finally:
            sock.close()

        if connect_ms is None:
            self.result.status = STATUS_BAD
            self.result.detail = f"连接 {self.host}:{self.port} 失败：{err}"
            self.result.message = f"端口 {self.port} 不可达，服务可能未启动或链路中断"
            self.result.hint = "请运维确认目标服务已启动、端口监听正常，并检查防火墙是否放行该端口"
            self.result.key_metrics = {"端口": str(self.port), "结果": "不可达"}
            return

        self.result.status = STATUS_OK
        self.result.key_metrics = {
            "端口": str(self.port),
            "结果": "可连接",
            "建连耗时": f"{connect_ms} ms",
        }
        self.result.detail = f"TCP 连接 {self.host}:{self.port} 成功，建连耗时 {connect_ms} ms"
        self.result.message = "端口可达，服务监听正常"


class EgressProbeTest(TcpProbeTest):
    """出口连通性：探测公网目标，判断本机出口/运营商链路是否正常。
    注：政务网如隔离公网，探测失败属正常，结果仅供参考。
    """
    name = "出口连通性（公网）"
