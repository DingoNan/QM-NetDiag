# -*- coding: utf-8 -*-
"""冒烟测试：验证核心测试模块与报告生成（不依赖外网）"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from core import PingTest, TcpProbeTest, Iperf3Test, TracerouteTest, DnsResolveTest, HttpProbeTest
from monitor import NetworkMonitor
from report import build_text_report, build_wechat_summary, build_html_report, evaluate_session, save_report
import platform_info

ok = 0
fail = 0

def check(name, cond, extra=""):
    global ok, fail
    mark = "PASS" if cond else "FAIL"
    if cond: ok += 1
    else: fail += 1
    print(f"[{mark}] {name} {extra}")

# 1. Ping 本地回环
r = PingTest("127.0.0.1", count=5).run()
check("PingTest", r.status in ("ok", "warn", "bad"), f"status={r.status} metrics={r.key_metrics}")

# 2. TCP 本地端口（大概率拒绝连接，属正常路径）
r = TcpProbeTest("127.0.0.1", 1, timeout=3).run()
check("TcpProbeTest", r.status in ("ok", "bad"), f"status={r.status}")

# 3. iperf3 工具定位
from core import find_iperf3
exe = find_iperf3()
check("find_iperf3", exe is not None and os.path.exists(exe), f"path={exe}")

# 4. 模拟完整会话并生成报告
session = {
    "tool_version": "1.0",
    "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "system_info": platform_info.get_system_info(),
    "target": {"host": "59.211.236.211", "port": 30014},
    "inner_target": "192.168.67.133:5201",
    "results": [
        {"name": "Ping 连通性测试", "status": "ok", "key_metrics": {"丢包": "0%", "平均延迟": "12 ms"},
         "detail": "发送 50 包，接收 50 包，丢包 0%", "message": "无丢包，连通性正常"},
        {"name": "TCP 端口探测", "status": "ok", "key_metrics": {"结果": "可连接"},
         "detail": "连接成功", "message": "端口可达"},
        {"name": "iperf3 带宽测试 · 单流上行", "status": "ok", "key_metrics": {"带宽": "23.2 Mbps", "重传率": "0.20%"},
         "detail": "上行带宽 23.2 Mbps", "message": "带宽正常"},
        {"name": "iperf3 带宽测试 · 8 流并行", "status": "ok", "key_metrics": {"带宽": "96.4 Mbps"},
         "detail": "并行带宽 96.4 Mbps", "message": "带宽正常"},
        {"name": "iperf3 带宽测试 · 反向（下行）", "status": "warn", "key_metrics": {"带宽": "18.5 Mbps", "重传率": "3.10%"},
         "detail": "下行带宽 18.5 Mbps，重传 3.1%", "message": "带宽略低于预期"},
        {"name": "路由追踪 Tracert", "status": "ok", "key_metrics": {"跳数": "12 跳"},
         "detail": "12 跳到达", "message": "路径正常"},
    ],
    "monitor_summary": {"samples": 20, "bad_ratio": 15.0, "level": "C", "verdict": "不稳定，存在频繁异常事件", "events": 3},
    "monitor_events": [
        {"time_str": "10:23:41", "type": "断连事件", "level": "bad", "detail": "Ping 全部超时且 TCP 连接失败"},
        {"time_str": "10:31:07", "type": "丢包事件", "level": "warn", "detail": "丢包 20%"},
        {"time_str": "10:44:52", "type": "延迟突增", "level": "warn", "detail": "延迟 486ms（基线 12ms）"},
    ],
}
concl = evaluate_session(session)
session["conclusion"] = concl
check("evaluate_session", "score" in concl, f"score={concl['score']} title={concl['title']}")

txt = build_text_report(session)
check("text_report", "网络自检报告" in txt and "断连事件" in txt, f"len={len(txt)}")

ws = build_wechat_summary(session)
check("wechat_summary", "📊" in ws, f"len={len(ws)}")

html = build_html_report(session)
check("html_report", "<html" in html and "测试明细" in html and "时间线" in html, f"len={len(html)}")

paths = save_report(session, os.path.join(os.path.dirname(__file__), "_smoke_out"))
check("save_report", os.path.exists(paths["html"]) and os.path.exists(paths["txt"]), str(paths))

print(f"\n结果：{ok} PASS / {fail} FAIL")
sys.exit(1 if fail else 0)
