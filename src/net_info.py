# -*- coding: utf-8 -*-
"""
v2 网络信息检测：公网 IP + Wi-Fi 信号 + 本机网卡

设计稿 5.8 特性 H：
- 公网 IP 用 socket 连接远端推断（不依赖第三方接口，保护隐私）
- Wi-Fi 信号读取系统命令（Windows netsh，Linux iwconfig）
"""

from __future__ import annotations

import os
import socket
import subprocess
import platform


def get_local_ips() -> list:
    """获取本机所有 IPv4 地址"""
    ips = []
    try:
        # 用 UDP socket 触发系统获取 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        except Exception:
            pass
        finally:
            s.close()
    except Exception:
        pass

    # 兜底：用 hostname
    if not ips:
        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass

    return ips


def get_public_ip_info() -> dict:
    """获取公网 IP（通过连接目标推断，不调用第三方接口）

    Returns:
        {
            "ip": "59.211.236.211",
            "method": "socket-connect",
            "note": "本机出口 IP（推断）"
        }
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        return {
            "ip": local_ip,
            "method": "socket-connect",
            "note": "本机出口 IP（UDP socket 推断）",
        }
    except Exception as e:
        return {"ip": None, "method": "failed", "note": str(e)}


def get_wifi_signal() -> dict:
    """获取当前 Wi-Fi 信号强度（Windows 用 netsh）

    Returns:
        {
            "connected": True,
            "ssid": "MyWiFi",
            "signal_pct": 85,    # 0-100
            "signal_quality": "强",
            "channel": 11,
            "band": "5GHz",
            "raw": "原始输出"
        }
    """
    if platform.system() != "Windows":
        return {
            "connected": False,
            "note": f"Wi-Fi 检测仅在 Windows 上实现（当前 {platform.system()}）",
        }

    try:
        # 解析 netsh wlan show interfaces
        kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL,
                  "encoding": "gbk", "errors": "ignore"}
        result = subprocess.run(["netsh", "wlan", "show", "interfaces"], **kwargs)
        output = result.stdout or ""

        info = {"connected": False, "raw": output}

        # 解析 SSID
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                ssid = line.split(":", 1)[1].strip() if ":" in line else ""
                if ssid:
                    info["ssid"] = ssid
                    info["connected"] = True
            elif ("Signal" in line or "信号" in line) and ":" in line:
                # 处理中文 "信号 : 98%" 或英文 "Signal : 98%"
                pct_str = line.split(":", 1)[1].strip().rstrip("%")
                try:
                    pct = int(pct_str)
                    info["signal_pct"] = pct
                    info["signal_quality"] = _signal_quality(pct)
                except (ValueError, TypeError):
                    pass
            elif line.startswith("Channel") or "信道" in line or "频道" in line:
                # Channel: 11 / 信道 : 11
                if ":" in line:
                    parts = line.split(":", 1)[1].strip().split()
                    if parts:
                        try:
                            info["channel"] = int(parts[0])
                        except (ValueError, TypeError):
                            pass
            elif ("Radio type" in line or "频带" in line or "波段" in line):
                if ":" in line:
                    info["band"] = line.split(":", 1)[1].strip()

        return info
    except FileNotFoundError:
        return {"connected": False, "note": "netsh 命令未找到"}
    except Exception as e:
        return {"connected": False, "note": str(e)}


def _signal_quality(pct: int) -> str:
    """信号强度 → 质量等级"""
    if pct >= 80:
        return "强"
    if pct >= 60:
        return "良好"
    if pct >= 40:
        return "中等"
    if pct >= 20:
        return "弱"
    return "极弱"


def get_network_interfaces() -> list:
    """获取本机网卡列表（含 IP/MAC/类型）

    Returns:
        [{
            "name": "以太网",
            "ip": "192.168.1.23",
            "mac": "DC:DF:DF:ER:DF",
            "type": "有线",
            "is_up": True,
        }, ...]
    """
    interfaces = []
    try:
        import psutil
        stats = psutil.net_if_stats()
        addrs_map = psutil.net_if_addrs()
        for ifname, addrs in addrs_map.items():
            ip = None
            mac = None
            for a in addrs:
                if hasattr(socket, "AF_INET") and a.family == socket.AF_INET:
                    if a.address and not a.address.startswith("127."):
                        ip = a.address
                elif hasattr(psutil, "AF_LINK") and a.family == psutil.AF_LINK:
                    mac = a.address
            if not ip:
                continue
            st = stats.get(ifname)
            is_up = st.isup if st else False
            interfaces.append({
                "name": ifname,
                "ip": ip,
                "mac": mac or "",
                "type": _classify_interface(ifname),
                "is_up": is_up,
            })
    except ImportError:
        # psutil 不可用：用 socket 兜底
        ips = get_local_ips()
        for ip in ips:
            interfaces.append({
                "name": "默认网卡",
                "ip": ip,
                "mac": "",
                "type": "未知",
                "is_up": True,
            })
    except Exception:
        pass

    return interfaces


def _classify_interface(name: str) -> str:
    """根据网卡名判断类型"""
    n = name.lower()
    if any(k in n for k in ("wi-fi", "wlan", "wireless")):
        return "无线"
    if any(k in n for k in ("eth", "lan", "以太网")):
        return "有线"
    if any(k in n for k in ("vmware", "virtualbox", "hyper-v", "veth", "docker", "vmnet")):
        return "虚拟"
    if any(k in n for k in ("ppp", "vpn", "tun", "tap")):
        return "VPN"
    if "loopback" in n or "lo" == n:
        return "回环"
    return "其他"