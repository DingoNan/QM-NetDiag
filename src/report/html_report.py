# -*- coding: utf-8 -*-
"""
HTML 报告生成：内嵌政务蓝风格模板，浏览器打开即可查看/打印 PDF。
使用占位符替换（避免 str.format 与 CSS 花括号冲突）。
"""
import html as html_mod
import os
import time

from .text_report import STATUS_SYMBOL

# 状态 → 颜色
_STATUS_COLOR = {"ok": "#2E9E5B", "warn": "#E6A23C", "bad": "#D64545",
                 "error": "#D64545", "skip": "#8A97A5", "aborted": "#8A97A5"}

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<style>
:root{--primary:#1B5E9E;--bg:#F5F7FA;--text:#2B3A4A;--muted:#8A97A5;--line:#E6EBF0}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei","PingFang SC","WenQuanYi Micro Hei",sans-serif;
     background:var(--bg);color:var(--text);font-size:14px;line-height:1.7;padding:28px}
.wrap{max-width:900px;margin:0 auto}
.header{background:linear-gradient(135deg,#14487A,#1B5E9E 55%,#2471B8);
        color:#fff;border-radius:14px;padding:22px 28px;margin-bottom:18px}
.header h1{font-size:21px;letter-spacing:.5px}
.header .sub{opacity:.8;font-size:12.5px;margin-top:3px}
.banner{border-radius:12px;padding:16px 22px;margin-bottom:18px;border:1px solid}
.banner h2{font-size:18px}
.banner p{font-size:13px;margin-top:2px}
.banner.ok{background:#E8F7EE;border-color:#BFE6CE;color:#1E7A45}
.banner.warn{background:#FDF3E3;border-color:#F5D9A8;color:#B06A12}
.banner.bad{background:#FDECEC;border-color:#F5C4C4;color:#B23A3A}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(27,94,158,.08);
      padding:18px 22px;margin-bottom:16px}
.card h3{font-size:15px;margin-bottom:12px;padding-left:10px;
         border-left:4px solid var(--primary)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#F4F7FA;color:var(--muted);text-align:left;padding:8px 12px;font-size:12px}
td{padding:8px 12px;border-bottom:1px solid #F0F3F6;vertical-align:top}
tr:last-child td{border-bottom:none}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.meta div{background:#FAFBFD;border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.meta .k{font-size:11px;color:var(--muted)}
.meta .v{font-size:13px;font-weight:600;word-break:break-all}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(27,94,158,.08);
      padding:14px 16px;border-top:3px solid var(--primary)}
.stat .k{font-size:12px;color:var(--muted)}
.stat .v{font-size:24px;font-weight:700}
.stat .v small{font-size:12px;color:var(--muted);font-weight:400}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 10px;border-radius:20px}
.tl{padding-left:6px}
.tl-item{position:relative;padding:0 0 14px 22px;border-left:2px solid var(--line)}
.tl-item::before{content:"";position:absolute;left:-7px;top:4px;width:12px;height:12px;
                 border-radius:50%;background:#fff;border:3px solid var(--primary)}
.tl-item.bad::before{border-color:#D64545}
.tl-item.warn::before{border-color:#E6A23C}
.tl-item .t{font-size:12px;color:var(--muted)}
.tl-item .d{font-size:13px;font-weight:600;margin:1px 0}
.tl-item .s{font-size:12px;color:var(--muted)}
.footer{margin-top:20px;color:var(--muted);font-size:11.5px;text-align:center}
@media print{body{padding:0}.card,.banner{box-shadow:none;page-break-inside:avoid}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>网络自检报告</h1>
    <div class="sub">国产化信创 · 一体化系统网络体检 ｜ NetDiag v__VERSION__ ｜ 生成时间 __GENERATED__</div>
  </div>
  __BANNER__
  <div class="card">
    <h3>测试环境</h3>
    <div class="meta">__META__</div>
  </div>
  <div class="card">
    <h3>核心指标</h3>
    <div class="stats">__STATS__</div>
  </div>
  __CHARTS__
  <div class="card">
    <h3>测试明细</h3>
    <table>
      <thead><tr><th style="width:26%">测试项</th><th>结果摘要</th><th style="width:14%">状态</th></tr></thead>
      <tbody>__ROWS__</tbody>
    </table>
  </div>
  __TIMELINE__
  <div class="footer">
    说明：带宽测试走运营商 NAT 映射链路（__TARGET__），结果受运营商线路质量影响。<br>
    本报告由本机工具本地生成，未上传任何数据 ｜ 设计：浅木·先生
  </div>
</div>
</body>
</html>
"""


def _esc(text) -> str:
    return html_mod.escape(str(text or ""))


def build_trend_svg(samples: list, width: int = 820, height: int = 230) -> str:
    """生成监测趋势折线图（纯内联 SVG，离线可渲染）。
    samples: [{time_str, avg_ms, tcp_ms, http_ms, reachable}] 按时间序。
    """
    if not samples:
        return ""
    pad_l, pad_r, pad_t, pad_b = 46, 14, 18, 34
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    n = len(samples)
    max_v = max([s.get("avg_ms", 0) for s in samples]
                + [s.get("tcp_ms", 0) for s in samples]
                + [s.get("http_ms", 0) for s in samples] + [100.0])
    max_v = max(max_v, 100.0)

    def x(i):
        return pad_l + (inner_w * i / max(1, n - 1))

    def y(v):
        return pad_t + inner_h * (1 - v / max_v)

    parts = []
    # 背景网格与 Y 轴刻度
    steps = 4
    for k in range(steps + 1):
        v = max_v * k / steps
        yy = y(v)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{width - pad_r}" y2="{yy:.1f}" '
                     f'stroke="#EDF1F5" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" text-anchor="end" '
                     f'fill="#98A2AE" font-size="10">{v:.0f}ms</text>')
    # 坐标轴
    parts.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height - pad_b}" stroke="#C4CCD6"/>')
    parts.append(f'<line x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}" stroke="#C4CCD6"/>')

    # 三条曲线：Ping 延迟 / TCP 建连 / HTTP 响应（每点带悬浮提示）
    series = [("avg_ms", "Ping 延迟", "#1B5E9E"),
              ("tcp_ms", "TCP 建连", "#2E9E5B"),
              ("http_ms", "HTTP 响应", "#E6A23C")]
    for field, label, color in series:
        pts = []
        for i, s in enumerate(samples):
            px, py = x(i), y(s.get(field, 0))
            pts.append(f"{px:.1f},{py:.1f}")
            val = s.get(field, 0)
            tip = f"{label}：{val:.0f}ms @ {s.get('time_str', '')}"
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.5" fill="{color}" '
                         f'opacity="0.9"><title>{_esc(tip)}</title></circle>')
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" '
                     f'stroke-linejoin="round" points="{" ".join(pts)}"/>')

    # X 轴时间标签：按采样间隔均匀划分（最多约 6 个刻度）+ 断连红叉
    step = max(1, n // 6)
    label_idx = set(range(0, n, step)) | {n - 1}
    for idx in sorted(label_idx):
        parts.append(f'<text x="{x(idx):.1f}" y="{height - 10:.0f}" text-anchor="middle" '
                     f'fill="#98A2AE" font-size="10">{_esc(samples[idx].get("time_str", ""))}</text>')
    for i, s in enumerate(samples):
        if not s.get("reachable", True):
            cx, cy = x(i), height - pad_b + 8
            parts.append(f'<text x="{cx:.1f}" y="{cy:.1f}" fill="#D64545" '
                         f'font-size="11" text-anchor="middle" font-weight="bold">✕</text>')

    # 图例
    lx = pad_l + 8
    for field, label, color in series:
        parts.append(f'<rect x="{lx}" y="8" width="12" height="4" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{lx + 16}" y="13" fill="#5B6675" font-size="10">{label}</text>')
        lx += 16 + len(label) * 12 + 18

    return (f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'xmlns="http://www.w3.org/2000/svg" style="background:#FAFBFD;border-radius:8px">'
            + "".join(parts) + "</svg>")


def build_bars_svg(items: list, unit: str = "", colors=None, width: int = 820) -> str:
    """通用横向条形图（纯内联 SVG）。items: [(label, value)]"""
    if not items:
        return ""
    row_h = 34
    height = len(items) * row_h + 40
    pad_l, pad_r = 118, 78
    inner_w = width - pad_l - pad_r
    max_v = max(v for _, v in items) or 1
    colors = colors or ["#1B5E9E"]
    parts = []
    if unit:
        parts.append(f'<text x="{pad_l}" y="16" fill="#98A2AE" font-size="10">单位：{unit}</text>')
    for i, (label, v) in enumerate(items):
        y0 = 26 + i * row_h
        bar_w = max(2, inner_w * v / max_v)
        parts.append(f'<text x="{pad_l - 8}" y="{y0 + 14}" text-anchor="end" fill="#5B6675" '
                     f'font-size="11">{_esc(label)}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y0}" width="{bar_w:.1f}" height="16" rx="3" '
                     f'fill="{colors[i % len(colors)]}"/>')
        parts.append(f'<text x="{pad_l + bar_w + 6}" y="{y0 + 14}" fill="#2B3A4A" '
                     f'font-size="11" font-weight="bold">{v:.1f} {unit}</text>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'xmlns="http://www.w3.org/2000/svg" style="background:#FAFBFD;border-radius:8px">'
            + "".join(parts) + "</svg>")


def _parse_mbps(value) -> float:
    """从 '12.4 Mbps' 提取数值"""
    try:
        return float(str(value).replace("Mbps", "").replace("M", "").strip())
    except (TypeError, ValueError):
        return 0.0


def load_previous_metrics(report_dir: str, report_type: str, subtype: str = "") -> dict:
    """读取同类型最近一份历史报告的关键指标（带宽估算/延迟），用于基线对比"""
    import re
    from config import report_type_name
    if not os.path.isdir(report_dir):
        return {}
    prefix = f"网络测试报告_{report_type_name(report_type, subtype)}"
    txts = [f for f in os.listdir(report_dir)
            if f.startswith(prefix) and f.endswith(".txt")]
    if not txts:
        return {}

    def ts_key(f):
        parts = f[:-4].split("_")
        return (parts[-2] + parts[-1]) if len(parts) >= 4 else ""

    txts.sort(key=ts_key)
    try:
        content = open(os.path.join(report_dir, txts[-1]), encoding="utf-8").read()
    except OSError:
        return {}
    result = {}
    m = re.search(r"带宽估算：上行约 ([\d.]+) Mbps、下行约 ([\d.]+) Mbps", content)
    if m:
        result["up"] = float(m.group(1))
        result["down"] = float(m.group(2))
    m = re.search(r"平均延迟 ([\d.]+) ms", content)
    if m:
        result["latency"] = float(m.group(1))
    m = re.search(r"丢包 ([\d.]+)%", content)
    if m:
        result["loss"] = float(m.group(1))
    return result


def build_compare_text(current: dict, prev: dict) -> str:
    """生成当前指标与历史基线的对比说明"""
    parts = []
    if prev.get("up") and current.get("up"):
        d = current["up"] - prev["up"]
        pct = d / prev["up"] * 100
        parts.append(f"上行 {prev['up']:.1f}→{current['up']:.1f} Mbps（{'+' if pct >= 0 else ''}{pct:.1f}%）")
    if prev.get("down") and current.get("down"):
        d = current["down"] - prev["down"]
        pct = d / prev["down"] * 100
        parts.append(f"下行 {prev['down']:.1f}→{current['down']:.1f} Mbps（{'+' if pct >= 0 else ''}{pct:.1f}%）")
    if prev.get("latency") and current.get("latency"):
        parts.append(f"延迟 {prev['latency']:.0f}→{current['latency']:.0f} ms")
    if prev.get("loss") is not None and current.get("loss") is not None:
        parts.append(f"丢包 {prev['loss']:.0f}%→{current['loss']:.0f}%")
    return "；".join(parts) + "（较上次检测）" if parts else ""


def locate_problem(session: dict, bandwidth: dict = None) -> tuple:
    """
    分层诊断：推断问题所在层级（借鉴 Network Doctor 的分层思想）。
    返回 (location, 通俗说明)。
    判定顺序：DNS 配置 > 本地/链路 > 目标服务端(端口) > 目标服务端(应用) > 带宽限制 > 正常
    """
    results = session.get("results", [])

    # 监测会话：优先按监测摘要定位（链路波动/不稳定）
    ms = session.get("monitor_summary")
    if ms and ms.get("level") in ("B", "C"):
        return "链路稳定性", (f"监测期间异常占比 {ms.get('bad_ratio', 0)}%，"
                               "链路存在不稳定波动（丢包/断连/延迟突增）")

    def status_of(prefix):
        for r in results:
            if r.get("name", "").startswith(prefix):
                return r.get("status")
        return None

    ping = status_of("Ping")
    tcp = status_of("TCP")
    dns = status_of("DNS")
    http = status_of("HTTP")
    tracert = status_of("路由追踪")

    if dns == "bad":
        return "DNS 配置", "DNS 解析失败，问题在本机 DNS 配置或 DNS 服务不可用"
    if ping == "bad" or tracert == "bad":
        return "本地网络/中间链路", "Ping 与 TCP 均不可达，问题在本地网络出口或中间链路"
    if tcp == "bad":
        return "目标服务端", "网络可达但目标端口不通，服务未启动、防火墙拦截或端口映射错误"
    if http == "bad":
        return "目标服务端", "端口可达但 HTTP 异常，问题在应用服务或服务器资源"
    if http == "warn":
        return "目标服务端", "HTTP 响应偏慢，重点检查服务器 CPU/内存/数据库"
    if bandwidth and bandwidth.get("est") and bandwidth["est"] < 20:
        return "带宽限制", (f"链路连通正常但带宽较低（约 {bandwidth['est']:.1f} Mbps），"
                            "属线路带宽限制而非链路故障")
    return "链路正常", "各项检查正常，未发现明显网络问题"


def evaluate_session(session: dict) -> dict:
    """根据各测试结果计算总体评分与结论，并自动估算带宽水平"""
    scores = {"ok": 100, "warn": 65, "bad": 25, "error": 0, "aborted": 0}
    results = session.get("results", [])
    valid = [r for r in results if r.get("status") not in ("skip", "aborted")]
    if not valid:
        if results and all(r.get("status") in ("skip", "aborted") for r in results):
            return {"score": 0, "title": "本次检测项均被跳过",
                    "suggestion": "所选检测项被跳过（如目标禁 ping），无可评估数据。可换用高级探测的其他单项测试。"}
        return {"score": 0, "title": "无有效测试结果", "suggestion": "请检查测试项是否正常执行"}
    score = round(sum(scores.get(r.get("status", "skip"), 0) for r in valid) / len(valid))
    any_bad = any(r.get("status") in ("bad", "error") for r in valid)
    any_warn = any(r.get("status") == "warn" for r in valid)
    if any_bad:
        title = "链路存在明显问题，建议报修"
        suggestion = ("存在异常测试项，建议：1) 检查本机网线/WiFi；2) 换网络复测一次；"
                      "3) 仍异常请将本报告发送运维，报修运营商线路。")
    elif any_warn:
        title = "存在轻微异常，建议持续关注"
        suggestion = "部分指标略低于预期，建议结合长时监测观察趋势；如经常性出现，建议报修排查。"
    else:
        title = "链路基本正常"
        suggestion = ("各项指标健康。如仍感觉系统缓慢，建议检查一体化系统服务器端资源"
                      "（CPU/内存/数据库），或由运维进行服务端性能采集。")
    ms = session.get("monitor_summary")
    if ms and ms.get("level") in ("B", "C"):
        title = "监测期间存在不稳定事件"
        suggestion = f"长时监测 {ms.get('samples', 0)} 次采样中异常占比 {ms.get('bad_ratio', 0)}%，" \
                     f"事件集中在报告时间线标注时段，建议重点排查该时段出口链路。"
    # 带宽自动估算与通俗说明（不依赖参考值）
    from core.iperf3_test import bandwidth_level
    bw = {}
    for r in results:
        name = r.get("name", "")
        if "iperf3" not in name:
            continue
        b = _parse_mbps(r.get("key_metrics", {}).get("带宽", 0))
        if "单流" in name:
            bw["up_single"] = b
        elif "并行" in name:
            bw["up_multi"] = b
        elif "反向" in name:
            bw["down"] = b
    if bw:
        up = bw.get("up_multi") or bw.get("up_single")
        down = bw.get("down")
        vals = [v for v in (up, down) if v]
        if vals:
            est = max(vals)
            level_text = bandwidth_level(est)
            summary = {"up": up, "down": down, "est": est, "level": level_text}
            # 结论建议附带宽说明
            bw_note = (f"带宽估算：上行约 {up:.1f} Mbps" if up else "带宽估算：上行未测") + \
                      (f"、下行约 {down:.1f} Mbps" if down else "") + f"（{level_text}）。"
            suggestion = bw_note + suggestion
        else:
            # 无有效带宽数据（iperf3 全部失败）
            summary = None
    else:
        summary = None
    # 分层诊断：问题定位
    location, location_text = locate_problem(session, summary)
    if location != "链路正常":
        title = f"问题定位：{location}"
        suggestion = f"【定位】{location_text}。" + suggestion
    return {"score": score, "title": title, "suggestion": suggestion,
            "bandwidth": summary, "location": location, "location_text": location_text}


def build_html_report(session: dict) -> str:
    """生成完整 HTML 报告字符串"""
    concl = session.get("conclusion") or evaluate_session(session)
    session["conclusion"] = concl

    # 结论横幅：颜色跟随语义（存在异常->红，警告->黄，中止->灰，全正常->绿）
    if session.get("aborted"):
        banner_cls, icon = "warn", "⏹"
    else:
        statuses = [r.get("status") for r in session.get("results", [])]
        if any(s in ("bad", "error") for s in statuses):
            banner_cls, icon = "bad", "🔴"
        elif any(s == "warn" for s in statuses):
            banner_cls, icon = "warn", "🟡"
        else:
            banner_cls, icon = "ok", "🟢"
    banner = (f'<div class="banner {banner_cls}"><h2>{icon} {_esc(concl["title"])}'
              f'（{concl["score"]} 分）</h2><p>{_esc(concl["suggestion"])}</p></div>')

    # 测试环境
    si = session.get("system_info", {})
    tgt = session.get("target", {})
    from config import report_type_name
    meta_items = [
        ("报告类型", report_type_name(session.get("report_type", "quick"),
                                     session.get("report_subtype", ""))),
        ("测试时间", session.get("start_time", "")),
        ("机器名称", si.get("hostname", "")),
        ("系统信息", f"{si.get('os_version', '')}（{si.get('arch_detail', '')}）"),
        ("本机 IP", ", ".join(si.get("local_ips", [])) or "未知"),
        ("本机 MAC", ", ".join(si.get("macs", [])) or "未知"),
        ("测试目标", f"{tgt.get('host', '')}:{tgt.get('port', '')}"),
        ("内网映射", session.get("inner_target", "")),
    ]
    if concl.get("location"):
        meta_items.append(("问题定位", concl["location"]))
    if session.get("compare_text"):
        meta_items.append(("与上次对比", session["compare_text"]))
    meta = "".join(f'<div><div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div></div>'
                   for k, v in meta_items)
    # 带宽估算行（自动评估）
    bw = concl.get("bandwidth")
    if bw:
        bw_line = (f"上行约 {bw['up']:.1f} Mbps" if bw.get("up") else "上行未测")
        if bw.get("down"):
            bw_line += f"，下行约 {bw['down']:.1f} Mbps"
        bw_line += f"｜{bw['level']}"
        meta += (f'<div><div class="k">带宽估算</div>'
                 f'<div class="v">{_esc(bw_line)}</div></div>')

    # 核心指标（取前 6 个关键指标，去重）
    stats = []
    seen = set()
    for r in session.get("results", []):
        for k, v in r.get("key_metrics", {}).items():
            key = f"{r.get('name')}·{k}"
            if key in seen:
                continue
            seen.add(key)
            color = _STATUS_COLOR.get(r.get("status"), "#1B5E9E")
            stats.append(f'<div class="stat" style="border-top-color:{color}">'
                         f'<div class="k">{_esc(key)}</div>'
                         f'<div class="v">{_esc(v)}</div></div>')
            if len(stats) >= 6:
                break
        if len(stats) >= 6:
            break
    stats_html = "".join(stats) or '<div class="stat"><div class="v">无数据</div></div>'

    # 快速/高级检测：带宽与延迟指标条形图（让报告图文并茂）
    charts = ""
    if session.get("report_type") != "monitor":
        bw_items = []
        lat_items = []
        import re as _re
        for r in session.get("results", []):
            name = r.get("name", "")
            km = r.get("key_metrics", {})
            if "iperf3" in name:
                v = _parse_mbps(km.get("带宽", 0))
                if v > 0:
                    sub = "单流上行" if "单流" in name else ("并行上行" if "并行" in name else "反向下行")
                    bw_items.append((sub, v))
            for key, label in (("平均延迟", "Ping 延迟"), ("建连耗时", "TCP 建连"),
                               ("平均响应", "HTTP 响应"), ("耗时", "DNS 解析")):
                if name.startswith(("Ping", "TCP", "HTTP", "DNS")) and key in km:
                    m = _re.search(r"[\d.]+", str(km[key]))
                    v = float(m.group(0)) if m else 0
                    if v > 0:
                        lat_items.append((label, v))
                    break
        if bw_items:
            charts += (f'<div class="card"><h3>📊 带宽对比（上行/下行）</h3>'
                       f'{build_bars_svg(bw_items, "Mbps", ["#1B5E9E", "#2471B8", "#2E8BC8"])}</div>')
        if lat_items:
            charts += (f'<div class="card"><h3>📊 延迟对比</h3>'
                       f'{build_bars_svg(lat_items, "ms", ["#2E9E5B", "#E6A23C", "#D64545", "#8A97A5"])}</div>')

    # 明细行（含修复提示）
    rows = []
    for r in session.get("results", []):
        color = _STATUS_COLOR.get(r.get("status"), "#8A97A5")
        badge = f'<span class="badge" style="background:{color}22;color:{color}">' \
                f'{STATUS_SYMBOL.get(r.get("status"), r.get("status"))}</span>'
        detail = r.get("detail") or r.get("message") or ""
        hint = r.get("hint", "")
        if hint:
            detail += (f'<div style="color:#B06A12;font-size:12px;margin-top:3px">'
                       f'💡 建议：{_esc(hint)}</div>')
        rows.append(f"<tr><td><b>{_esc(r.get('name', ''))}</b></td>"
                    f"<td>{detail}</td><td>{badge}</td></tr>")
    rows_html = "".join(rows)

    # 监测时间线 + 趋势图
    timeline_html = ""
    ms = session.get("monitor_summary")
    events = session.get("monitor_events", [])
    samples = session.get("monitor_samples", [])
    if ms:
        # 趋势折线图（Ping/TCP/HTTP 耗时随时间变化）
        trend = build_trend_svg(samples)
        if trend:
            timeline_html += (f'<div class="card"><h3>📈 监测趋势（延迟/耗时随时间变化）</h3>'
                              f'{trend}</div>')
        items = []
        for ev in events:
            cls = "bad" if ev.get("level") == "bad" else "warn"
            lv = "严重" if ev.get("level") == "bad" else "中等"
            items.append(f'<div class="tl-item {cls}"><div class="t">{_esc(ev.get("time_str", ""))}'
                         f' · {_esc(ev.get("type", ""))}（{lv}）</div>'
                         f'<div class="s">{_esc(ev.get("detail", ""))}</div></div>')
        items.append(f'<div class="tl-item"><div class="t">监测结束</div>'
                     f'<div class="s">采样 {ms.get("samples", 0)} 次 · 异常占比 {ms.get("bad_ratio", 0)}%'
                     f' · 评级 {ms.get("level", "-")}（{ms.get("verdict", "")}）</div></div>')
        timeline_html += (f'<div class="card"><h3>长时监测 · 不稳定事件时间线</h3>'
                         f'<div class="tl">{"".join(items)}</div></div>')

    return (_TEMPLATE
            .replace("__TITLE__", f"网络测试报告_{_esc(si.get('hostname', 'machine'))}"
                                  f"_{time.strftime('%Y%m%d_%H%M%S')}")
            .replace("__VERSION__", _esc(session.get("tool_version", "1.0")))
            .replace("__GENERATED__", _esc(session.get("start_time", "")))
            .replace("__BANNER__", banner)
            .replace("__META__", meta)
            .replace("__STATS__", stats_html)
            .replace("__CHARTS__", charts)
            .replace("__ROWS__", rows_html)
            .replace("__TIMELINE__", timeline_html)
            .replace("__TARGET__", f"{_esc(tgt.get('host', ''))}:{_esc(tgt.get('port', ''))}"))


def save_report(session: dict, directory: str = "结果") -> dict:
    """保存 HTML + TXT 报告，返回文件路径字典"""
    from .text_report import build_text_report
    os.makedirs(directory, exist_ok=True)
    hostname = session.get("system_info", {}).get("hostname", "machine")
    ts = time.strftime("%Y%m%d_%H%M%S")
    from config import report_type_name
    type_name = report_type_name(session.get("report_type", "quick"),
                                session.get("report_subtype", ""))
    base = os.path.join(directory, f"网络测试报告_{type_name}_{hostname}_{ts}")
    html_path = base + ".html"
    txt_path = base + ".txt"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html_report(session))
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(build_text_report(session))
    return {"html": html_path, "txt": txt_path}
