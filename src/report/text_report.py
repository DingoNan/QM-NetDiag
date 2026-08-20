# -*- coding: utf-8 -*-
"""
TXT 日志与微信摘要生成。
TXT 报告供运维同事阅读归档；微信摘要为纯文本一行，方便直接粘贴发送。
"""

STATUS_SYMBOL = {
    "ok": "✅ 正常",
    "warn": "⚠️ 异常",
    "bad": "❌ 异常",
    "error": "❌ 失败",
    "skip": "⏭️ 跳过",
    "aborted": "⏹ 中止",
}


def _fmt_metrics(metrics: dict) -> str:
    return " ｜ ".join(f"{k} {v}" for k, v in metrics.items())


def build_text_report(session: dict) -> str:
    """生成完整 TXT 报告文本"""
    lines = []
    line = "=" * 62
    lines.append(line)
    lines.append("   网络自检报告")
    lines.append("   NetDiag v" + session.get("tool_version", "1.0"))
    lines.append(line)
    si = session.get("system_info", {})
    tgt = session.get("target", {})
    from config import report_type_name
    lines.append(f"测试时间：{session.get('start_time', '')}")
    lines.append(f"报告类型：{report_type_name(session.get('report_type', 'quick'), session.get('report_subtype', ''))}")
    lines.append(f"机器名称：{si.get('hostname', '')}")
    lines.append(f"系统信息：{si.get('os_version', '')} ({si.get('arch_detail', '')})")
    lines.append(f"本机 IP ：{', '.join(si.get('local_ips', [])) or '未知'}")
    lines.append(f"本机 MAC：{', '.join(si.get('macs', [])) or '未知'}")
    lines.append(f"测试目标：{tgt.get('host', '')}:{tgt.get('port', '')}"
                 f"（NAT 映射 → 内网 {session.get('inner_target', '')}）")
    # 带宽估算（自动评估）
    bw = session.get("conclusion", {}).get("bandwidth")
    if bw:
        bw_line = (f"上行约 {bw['up']:.1f} Mbps" if bw.get("up") else "上行未测")
        if bw.get("down"):
            bw_line += f"，下行约 {bw['down']:.1f} Mbps"
        lines.append(f"带宽估算：{bw_line}（{bw['level']}）")
    if session.get("compare_text"):
        lines.append(f"与上次对比：{session['compare_text']}")
    lines.append(line)

    # 总体结论
    concl = session.get("conclusion", {})
    lines.append(f"总体结论：【{concl.get('title', '')}】 评分 {concl.get('score', 0)} 分")
    if concl.get("location"):
        lines.append(f"问题定位：{concl['location']}（{concl.get('location_text', '')}）")
    lines.append(f"建议：{concl.get('suggestion', '')}")
    lines.append(line)

    # 各项测试
    lines.append("【测试明细】")
    for r in session.get("results", []):
        status = STATUS_SYMBOL.get(r.get("status", "skip"), r.get("status", ""))
        lines.append(f"  {status}  {r.get('name', '')}")
        if r.get("key_metrics"):
            lines.append(f"      指标：{_fmt_metrics(r['key_metrics'])}")
        if r.get("detail"):
            lines.append(f"      详情：{r['detail']}")
        if r.get("message"):
            lines.append(f"      判定：{r['message']}")
        if r.get("hint"):
            lines.append(f"      建议：{r['hint']}")
    lines.append(line)

    # 监测
    ms = session.get("monitor_summary")
    if ms:
        lines.append("【长时监测】")
        lines.append(f"  采样 {ms.get('samples', 0)} 次，异常占比 {ms.get('bad_ratio', 0)}%，"
                     f"稳定性评级 {ms.get('level', '-')}（{ms.get('verdict', '')}），"
                     f"捕获事件 {ms.get('events', 0)} 个")
        # 趋势摘要（延迟/耗时波动范围）
        samples = session.get("monitor_samples", [])
        if samples:
            def _range(key):
                vals = [s.get(key, 0) for s in samples if s.get(key, 0) > 0]
                if not vals:
                    return None
                return f"{min(vals):.0f}~{max(vals):.0f}ms（均值 {sum(vals) / len(vals):.0f}ms）"
            trend = []
            for key, label in (("avg_ms", "Ping 延迟"), ("tcp_ms", "TCP 建连"),
                               ("http_ms", "HTTP 响应")):
                r = _range(key)
                if r:
                    trend.append(f"{label} {r}")
            if trend:
                lines.append("  趋势：" + "；".join(trend))
        for ev in session.get("monitor_events", []):
            lv = "严重" if ev.get("level") == "bad" else "中等"
            lines.append(f"  [{ev.get('time_str', '')}] {ev.get('type', '')}（{lv}）：{ev.get('detail', '')}")
        lines.append(line)

    lines.append("说明：带宽测试走运营商 NAT 映射链路，结果受运营商线路质量影响。")
    lines.append("报告由本机工具本地生成，未上传任何数据。")
    lines.append("生成工具：网络自检工具 NetDiag v" + session.get("tool_version", "1.0"))
    lines.append("设计：浅木·先生")
    return "\n".join(lines)


def build_wechat_summary(session: dict) -> str:
    """一行式微信摘要"""
    si = session.get("system_info", {})
    tgt = session.get("target", {})
    concl = session.get("conclusion", {})
    parts = [f"📊 网络自检报告 {session.get('start_time', '')}",
             f"机器 {si.get('hostname', '')}",
             f"目标 {tgt.get('host', '')}:{tgt.get('port', '')}"]
    for r in session.get("results", []):
        st = r.get("status")
        if st in ("skip", "aborted"):
            continue
        for k, v in r.get("key_metrics", {}).items():
            parts.append(f"{r.get('name', '')}·{k} {v}")
        parts.append(f"{r.get('name', '')} {'✅' if st == 'ok' else '⚠️' if st == 'warn' else '❌'}")
    ms = session.get("monitor_summary")
    if ms:
        parts.append(f"监测 {ms.get('samples', 0)} 次/异常 {ms.get('bad_ratio', 0)}%")
    if session.get("aborted"):
        parts.append("⏹ 测试已中止（仅部分结果）")
    parts.append(f"结论：{concl.get('title', '')}")
    return " ｜ ".join(parts)
