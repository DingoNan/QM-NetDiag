# -*- coding: utf-8 -*-
"""
平台识别模块：自动识别操作系统与 CPU 架构，供系统自检与报告使用。
"""
import os
import platform
import re
import subprocess
import sys
import time

# 平台包类型定义
PACKAGE_WIN32 = "win32"
PACKAGE_WIN64 = "win64"
PACKAGE_KYLIN_X64 = "kylin_x64"
PACKAGE_KYLIN_ARM64 = "kylin_arm64"
PACKAGE_MAC_INTEL = "macos_x64"
PACKAGE_MAC_APPLE = "macos_arm64"


def detect_os() -> str:
    """返回操作系统类别: windows / linux / macos / other"""
    sys_name = platform.system().lower()
    if sys_name.startswith("win"):
        return "windows"
    if sys_name.startswith("linux"):
        return "linux"
    if sys_name.startswith("darwin"):
        return "macos"
    return "other"


def detect_arch() -> str:
    """返回 CPU 架构类别: x86 / x86_64 / arm64 / other"""
    machine = platform.machine().lower()
    if machine in ("x86", "i386", "i686"):
        return "x86"
    if machine in ("amd64", "x86_64", "x64"):
        return "x86_64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    if machine in ("armv7l", "armv6l"):
        return "arm32"
    return machine or "other"


def detect_os_version() -> str:
    """返回操作系统详细版本信息"""
    os_name = detect_os()
    try:
        if os_name == "windows":
            ver = platform.platform(aliased=True, terse=False)
            return ver
        if os_name == "linux":
            # 优先读取麒麟/统信等发行版信息
            for path in ("/etc/kylin-release", "/etc/os-release",
                         "/etc/redhat-release", "/etc/lsb-release"):
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        content = f.read().strip()
                    if path.endswith("os-release"):
                        for line in content.splitlines():
                            if line.startswith("PRETTY_NAME="):
                                return line.split("=", 1)[1].strip().strip('"')
                    if content:
                        return content.splitlines()[0]
                except OSError:
                    continue
            return platform.platform()
        if os_name == "macos":
            return "macOS " + platform.mac_ver()[0]
    except Exception:
        pass
    return platform.platform()


def detect_linux_distro() -> str:
    """返回 Linux 发行版名称（麒麟/统信/其他）"""
    if detect_os() != "linux":
        return ""
    try:
        if os.path.exists("/etc/kylin-release"):
            return "Kylin"
        with open("/etc/os-release", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.split("=", 1)[1].strip().strip('"').lower()
    except OSError:
        pass
    return ""


def get_local_ips() -> list:
    """获取本机 IPv4 地址列表（尽力而为，失败返回空列表）"""
    ips = []
    try:
        import socket
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    # 兜底：调用系统命令
    if not ips:
        try:
            os_name = detect_os()
            if os_name == "windows":
                out = subprocess.run(["ipconfig"], capture_output=True,
                                     text=True, timeout=10).stdout
                import re
                ips = re.findall(r"IPv4.*?:\s*([\d.]+)", out)
            else:
                out = subprocess.run(["hostname", "-I"], capture_output=True,
                                     text=True, timeout=10).stdout
                ips = [ip for ip in out.split() if "." in ip]
        except Exception:
            pass
    return ips


def get_hostname() -> str:
    """返回机器名"""
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "unknown"


def match_package_type() -> str:
    """
    识别当前系统应使用哪个平台包。
    返回 PACKAGE_* 常量；无法识别返回 ""。
    """
    os_name = detect_os()
    arch = detect_arch()
    if os_name == "windows":
        return PACKAGE_WIN64 if arch in ("x86_64", "x64") else PACKAGE_WIN32 if arch == "x86" else ""
    if os_name == "linux":
        if arch == "x86_64":
            return PACKAGE_KYLIN_X64
        if arch == "arm64":
            return PACKAGE_KYLIN_ARM64
        return ""
    if os_name == "macos":
        return PACKAGE_MAC_APPLE if arch == "arm64" else PACKAGE_MAC_INTEL if arch == "x86_64" else ""
    return ""


def get_macs() -> list:
    """获取本机网卡 MAC 地址列表（排除回环与全零）"""
    macs = []
    try:
        if os.name == "nt":
            out = subprocess.run(["getmac", "/fo", "csv", "/nh"],
                                 capture_output=True, timeout=15).stdout
            text = decode_bytes(out)
            for line in text.splitlines():
                parts = [p.strip().strip('"') for p in line.split('"') if p.strip()]
                # getmac CSV: 连接名, 网卡名, 物理地址
                for part in parts:
                    if re.fullmatch(r"[0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5}", part):
                        mac = part.upper()
                        if mac not in macs:
                            macs.append(mac)
        else:
            net_dir = "/sys/class/net"
            if os.path.isdir(net_dir):
                for name in sorted(os.listdir(net_dir)):
                    if name == "lo":
                        continue
                    try:
                        with open(os.path.join(net_dir, name, "address"),
                                  encoding="utf-8") as f:
                            mac = f.read().strip().upper()
                        if mac and mac != "00:00:00:00:00:00" and mac not in macs:
                            macs.append(mac)
                    except OSError:
                        continue
    except Exception:  # noqa: BLE001
        pass
    return macs


def get_system_info() -> dict:
    """汇总系统信息字典（用于报告头与自检提示）"""
    info = {
        "os_name": detect_os(),
        "os_version": detect_os_version(),
        "distro": detect_linux_distro(),
        "arch": detect_arch(),
        "arch_detail": platform.machine(),
        "hostname": get_hostname(),
        "local_ips": get_local_ips(),
        "macs": get_macs(),
        "python_version": platform.python_version(),
        "package_type": match_package_type(),
    }
    return info


def run_cmd(args, timeout=120, cwd=None, env=None, record_pid=False, stop_event=None):
    """
    通用子进程调用，返回 SimpleNamespace(returncode/stdout/stderr)。
    - 超时自动 kill 子进程，避免残留
    - record_pid=True 时把子进程 PID 记入残留清单（供启动自检）
    - stop_event: 用户中止信号（threading.Event），置位后 0.2s 内 kill 子进程
      （returncode=-3 表示被用户中止）
    """
    import types
    if cwd:
        cwd = os.path.abspath(cwd)
    try:
        popen_kw = {}
        if os.name == "nt":
            # 隐藏子进程控制台窗口（否则 iperf3.exe 等会弹出黑窗口）
            popen_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env, text=False, **popen_kw)
    except FileNotFoundError:
        return types.SimpleNamespace(returncode=-1, stdout=b"", stderr=b"")
    if record_pid:
        record_child_pid(proc.pid)
    deadline = time.time() + timeout
    while True:
        if stop_event is not None and stop_event.is_set():
            # 用户中止：立即结束子进程
            try:
                proc.kill()
            except OSError:
                pass
            out, err = proc.communicate()
            return types.SimpleNamespace(returncode=-3, stdout=out, stderr=err)
        if time.time() > deadline:
            # 超时：强制结束子进程
            try:
                proc.kill()
            except OSError:
                pass
            out, err = proc.communicate()
            return types.SimpleNamespace(returncode=-2, stdout=out, stderr=err)
        try:
            out, err = proc.communicate(timeout=0.2)
            return types.SimpleNamespace(returncode=proc.returncode, stdout=out, stderr=err)
        except subprocess.TimeoutExpired:
            continue


def decode_bytes(data: bytes) -> str:
    """智能解码子进程输出：优先 utf-8，失败回退 gbk/latin-1"""
    if not data:
        return ""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


# ---------- 子进程残留管理（供程序自检） ----------

def _pid_file() -> str:
    """残留 PID 清单文件：程序旁 .nettest_pids"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, ".nettest_pids")


def record_child_pid(pid: int):
    """记录子进程 PID（追加）"""
    try:
        with open(_pid_file(), "a", encoding="utf-8") as f:
            f.write(str(pid) + "\n")
    except OSError:
        pass


def clear_pid_file():
    """测试正常结束后清除残留清单"""
    try:
        os.remove(_pid_file())
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    """探测进程是否存活。
    注意：Windows 上 os.kill(pid, 0) 等于发送 CTRL_C_EVENT，
    会中断同控制台进程（含自身），因此必须用 OpenProcess 探测。
    """
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:  # noqa: BLE001
            # 兜底：tasklist 查询
            try:
                out = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, timeout=15).stdout
                return str(pid).encode() in out
            except Exception:  # noqa: BLE001
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _pid_is_iperf3(pid: int) -> bool:
    """校验 PID 对应进程是否为 iperf3（避免 PID 复用误判其他进程）"""
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                 capture_output=True, timeout=10).stdout
            return b"iperf3" in out.lower()
        except Exception:  # noqa: BLE001
            return False
    else:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                return b"iperf3" in f.read()
        except OSError:
            return False


def check_stale_processes() -> list:
    """返回仍存活的残留 iperf3 子进程 PID 列表（用于启动自检）。
    仅识别 iperf3 进程，避免旧 PID 被系统复用导致误报。
    """
    pids = []
    try:
        with open(_pid_file(), encoding="utf-8") as f:
            pids = [int(x) for x in f.read().split() if x.strip().isdigit()]
    except OSError:
        return []
    return [pid for pid in pids if _pid_alive(pid) and _pid_is_iperf3(pid)]


def kill_process(pid: int):
    """强制结束指定 PID 的进程"""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, timeout=15)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


if __name__ == "__main__":
    import json
    print(json.dumps(get_system_info(), ensure_ascii=False, indent=2))
