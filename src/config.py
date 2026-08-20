# -*- coding: utf-8 -*-
"""
配置管理模块：读写程序旁的 config.ini（configparser），支持缺省默认值。
配置文件采用 UTF-8 编码，Windows/麒麟/macOS 通用。
"""
import configparser
import os
import sys

# 报告类型（会话标记，用于文件名与历史页分类）
REPORT_TYPE_NAMES = {
    "quick": "快速检测",
    "advanced": "高级探测",
    "monitor": "长期监测",
}


def report_type_name(key: str, subtype: str = "") -> str:
    """报告类型显示名：支持子类型，如 高级探测·仅带宽 / 长期监测·3分钟"""
    base = REPORT_TYPE_NAMES.get(key or "quick", "快速检测")
    if subtype:
        return f"{base}·{subtype}"
    return base


DEFAULT_CONFIG = {
    "目标": {
        "外网映射地址": "59.211.236.211",
        "外网映射端口": "30014",
        "iperf3服务器地址": "",
        "iperf3服务器端口": "5201",
        "内网真实地址": "192.168.67.133",
        "内网真实端口": "5201",
        # 测试源 IP（本机多网卡时指定；留空自动选择）
        "测试源IP": "",
        "一体化系统地址": "",
        # 参考带宽留空 = 自动评估带宽水平（不预设，避免误判）
        "参考带宽Mbps": "",
        # 出口检测（公网目标，判断出口链路；政务网隔离公网时留空关闭）
        "出口检测地址": "223.5.5.5",
        "出口检测端口": "53",
    },
    "测试参数": {
        "ping次数": "50",
        "iperf时长秒": "30",
        "并行流数": "8",
        "监测间隔秒": "30",
        "监测默认分钟": "10",
        "报告目录": "结果",
    },
    "定时检测": {
        "启用": "否",
        "时间": "08:30",
    },
    "外观": {
        "主题": "政务蓝",
    },
}


def app_dir() -> str:
    """程序所在目录：源码运行时为 src/ 上级，打包后为 exe 所在目录"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包
        return os.path.dirname(sys.executable)
    # 源码运行：本文件在 src/ 下，配置在项目根
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(name: str) -> str:
    """资源文件路径（图标等，位于程序旁 assets/ 目录）"""
    return os.path.join(app_dir(), "assets", name)


def default_config_path() -> str:
    return os.path.join(app_dir(), "config.ini")


class AppConfig:
    """配置读写封装"""

    def __init__(self, path: str = None):
        self.path = path or default_config_path()
        self.parser = configparser.ConfigParser(allow_no_value=False)
        self.parser.optionxform = str  # 保持键大小写与中文
        self.load()

    def load(self):
        # 先写入默认值（不落盘），再读取真实文件覆盖
        self._fill_defaults()
        if os.path.exists(self.path):
            try:
                self.parser.read(self.path, encoding="utf-8")
            except (configparser.Error, OSError) as exc:
                print("配置文件读取失败，使用默认值:", exc)

    def _fill_defaults(self):
        for section, options in DEFAULT_CONFIG.items():
            if not self.parser.has_section(section):
                self.parser.add_section(section)
            for key, value in options.items():
                if not self.parser.has_option(section, key):
                    self.parser.set(section, key, value)

    def get(self, section: str, key: str, default: str = "") -> str:
        if self.parser.has_option(section, key):
            return self.parser.get(section, key).strip()
        return default

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        try:
            return int(self.get(section, key, str(default)))
        except ValueError:
            return default

    def set(self, section: str, key: str, value: str):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, str(value))

    def save(self, path: str = None):
        """保存配置到文件（UTF-8，保留中文）"""
        target = path or self.path
        try:
            with open(target, "w", encoding="utf-8") as f:
                self.parser.write(f)
            return True
        except OSError as exc:
            print("配置保存失败:", exc)
            return False

    # ---- 便捷属性 ----
    @property
    def target_host(self) -> str:
        return self.get("目标", "外网映射地址", "59.211.236.211")

    @property
    def target_port(self) -> int:
        return self.get_int("目标", "外网映射端口", 30014)

    @property
    def inner_host(self) -> str:
        return self.get("目标", "内网真实地址", "192.168.67.133")

    @property
    def inner_port(self) -> int:
        return self.get_int("目标", "内网真实端口", 5201)

    @property
    def iperf3_host(self) -> str:
        """iperf3 服务器地址：默认与外网映射一致（旧版配置兼容）"""
        v = self.get("目标", "iperf3服务器地址", "").strip()
        return v or self.target_host

    @property
    def iperf3_port(self) -> int:
        return self.get_int("目标", "iperf3服务器端口", 5201)

    @property
    def app_host(self) -> str:
        return self.get("目标", "一体化系统地址", "")

    @property
    def reference_bandwidth(self) -> int:
        """参考带宽；0/留空表示自动评估（不参与判定）"""
        return self.get_int("目标", "参考带宽Mbps", 0)

    @property
    def egress_host(self) -> str:
        """出口检测地址（公网目标）；留空则不检测"""
        return self.get("目标", "出口检测地址", "223.5.5.5").strip()

    @property
    def egress_port(self) -> int:
        return self.get_int("目标", "出口检测端口", 53)

    @property
    def sched_enabled(self) -> bool:
        return self.get("定时检测", "启用", "否").strip() in ("是", "1", "true", "True")

    @property
    def sched_time(self) -> str:
        return self.get("定时检测", "时间", "08:30").strip()

    @property
    def source_ip(self) -> str:
        return self.get("目标", "测试源IP", "").strip()

    @property
    def ping_count(self) -> int:
        return self.get_int("测试参数", "ping次数", 50)

    @property
    def iperf_duration(self) -> int:
        return self.get_int("测试参数", "iperf时长秒", 30)

    @property
    def parallel_streams(self) -> int:
        return self.get_int("测试参数", "并行流数", 8)

    @property
    def monitor_interval(self) -> int:
        return self.get_int("测试参数", "监测间隔秒", 30)

    @property
    def report_dir(self) -> str:
        d = self.get("测试参数", "报告目录", "结果")
        if not os.path.isabs(d):
            d = os.path.join(app_dir(), d)
        return d
