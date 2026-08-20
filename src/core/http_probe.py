# -*- coding: utf-8 -*-
"""
HTTP 探测：对一体化系统地址发起 GET 请求，测响应时间，模拟真实"系统缓慢"体感。
使用 urllib（标准库），兼容 HTTP/HTTPS，离线不依赖第三方库。
政务内网 HTTPS 常为自签名证书：默认忽略证书校验（否则证书不受信任会被误判为不可达）。
"""
import ssl
import time
import urllib.error
import urllib.request

from .base_test import BaseTest, STATUS_OK, STATUS_WARN, STATUS_BAD, STATUS_SKIP


def _asn1_read(data: bytes, off: int):
    """极简 ASN.1 TLV 读取，返回 (tag, value_bytes, next_off)"""
    tag = data[off]
    off += 1
    ln = data[off]
    off += 1
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(data[off:off + n], "big")
        off += n
    return tag, data[off:off + ln], off + ln


def _parse_cert_not_after(der: bytes):
    """从 DER 证书提取有效期至（notAfter），纯标准库实现。
    返回 UTC 字符串（UTCTime/GeneralizedTime 原文）；失败返回 None。
    """
    try:
        _, top, _ = _asn1_read(der, 0)
        _, tbs, _ = _asn1_read(top, 0)  # 顶层 SEQUENCE 的第一个字段 = tbsCertificate
        off = 0
        if tbs[0] == 0xA0:  # 可选 version 字段
            _, _, off = _asn1_read(tbs, off)
        for _ in range(3):  # serial / signatureAlgorithm / issuer
            _, _, off = _asn1_read(tbs, off)
        _, validity, _ = _asn1_read(tbs, off)  # 有效期序列（notBefore, notAfter）
        times = []
        voff = 0
        while voff < len(validity):
            t, v, nxt = _asn1_read(validity, voff)
            if t in (0x17, 0x18):  # UTCTime / GeneralizedTime
                times.append(v)
            voff = nxt
        return times[1] if len(times) >= 2 else None
    except Exception:  # noqa: BLE001
        return None


def _format_cert_time(raw: bytes) -> str:
    """将证书时间（UTCTime/GeneralizedTime）格式化为 YYYY-MM-DD HH:MM"""
    try:
        s = raw.decode("ascii", "ignore").rstrip("Z")
        if len(s) == 12:  # UTCTime: YYMMDDHHMMSS（YY<50 -> 20YY）
            yy = int(s[0:2])
            year = 2000 + yy if yy < 50 else 1900 + yy
            return f"{year}-{s[2:4]}-{s[4:6]} {s[6:8]}:{s[8:10]}"
        if len(s) >= 14:  # GeneralizedTime: YYYYMMDDHHMMSS
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
        return raw.decode("ascii", "ignore")
    except Exception:  # noqa: BLE001
        return raw.decode("ascii", "ignore")


class HttpProbeTest(BaseTest):
    name = "HTTP 探测"

    def __init__(self, url: str = "", timeout: float = 20, samples: int = 3,
                 ignore_ssl: bool = True):
        super().__init__(timeout=timeout * samples + 10)
        self.url = (url or "").strip()
        self.samples = max(1, samples)
        self.ignore_ssl = ignore_ssl
        if self.ignore_ssl:
            # 不校验证书：兼容政务内网自签名/不受信任证书
            self._opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(
                    context=ssl._create_unverified_context()))
        else:
            self._opener = urllib.request.build_opener()

    def _do_run(self):
        if not self.url:
            self.result.status = STATUS_SKIP
            self.result.message = "未配置一体化系统地址，已跳过（可在设置中填写）"
            return

        if not self.url.startswith(("http://", "https://")):
            self.url = "http://" + self.url

        times = []
        errors = []
        cert_not_after = ""
        for _ in range(self.samples):
            req = urllib.request.Request(
                self.url, headers={"User-Agent": "NetDiag/1.0"})
            start = time.time()
            try:
                with self._opener.open(req, timeout=self.timeout) as resp:
                    times.append(round((time.time() - start) * 1000, 1))
                    status_code = resp.status
                    # TLS 证书深度检测：有效期（自签名证书同样可读取，DER 解析不依赖验证）
                    try:
                        sock = resp.fp.raw._sock
                        der = sock.getpeercert(binary_form=True)
                        raw = _parse_cert_not_after(der)
                        if raw:
                            cert_not_after = _format_cert_time(raw)
                    except Exception:  # noqa: BLE001
                        pass
            except urllib.error.HTTPError as exc:
                # 4xx/5xx 也算"可达"，记录状态码
                times.append(round((time.time() - start) * 1000, 1))
                status_code = exc.code
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                status_code = None
            time.sleep(0.5)

        ssl_note = "（已忽略证书校验，适用于自签名证书）" if self.ignore_ssl else ""
        if not times:
            self.result.status = STATUS_BAD
            self.result.detail = f"{self.url} 访问失败：{'；'.join(errors)}{ssl_note}"
            self.result.message = "一体化系统无法访问，请检查应用服务是否正常"
            self.result.hint = "确认服务已启动、端口正确；HTTPS 场景已忽略证书校验，如仍失败检查端口/防火墙"
            self.result.key_metrics = {"地址": self.url, "结果": "不可达"}
            return

        avg = round(sum(times) / len(times), 1)
        self.result.key_metrics = {
            "地址": self.url,
            "平均响应": f"{avg} ms",
            "HTTP 状态": str(status_code),
        }
        if cert_not_after:
            self.result.key_metrics["证书有效期至"] = cert_not_after
        self.result.detail = (
            f"访问 {self.url} {self.samples} 次，响应 {times} ms，"
            f"平均 {avg} ms（HTTP {status_code}）{ssl_note}")
        if cert_not_after:
            self.result.detail += f"｜HTTPS 证书有效期至 {cert_not_after}"
        if avg > 5000:
            self.result.status = STATUS_BAD
            self.result.message = "响应极慢（>5s），符合「系统缓慢」症状，建议检查应用与数据库"
            self.result.hint = "重点检查服务器 CPU/内存/数据库连接数，必要时抓包确认耗时分布"
        elif avg > 2000:
            self.result.status = STATUS_WARN
            self.result.message = "响应偏慢（>2s），建议进一步排查"
            self.result.hint = "检查服务器资源与数据库慢查询；如为间歇性，用长期监测持续观察"
        else:
            self.result.status = STATUS_OK
            self.result.message = "系统响应正常"
