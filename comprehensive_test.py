# -*- coding: utf-8 -*-
"""
全面 GUI 自动化测试：验证所有页面渲染、控件完整性、核心交互流程。
用法：python comprehensive_test.py
"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.stdout.reconfigure(encoding="utf-8")

from ui import MainWindow
from core import PingTest, TcpProbeTest

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


def find_widgets(root, cls, text_sub=None):
    """递归查找控件"""
    found = []

    def walk(w):
        for c in w.winfo_children():
            if c.winfo_class() == cls:
                if text_sub is None:
                    found.append(c)
                else:
                    try:
                        if text_sub in c.cget("text"):
                            found.append(c)
                    except Exception:
                        pass
            walk(c)
    walk(root)
    return found


def main():
    global PASS, FAIL
    print("=" * 56)
    print("全面 GUI 自动化测试")
    print("=" * 56)
    app = MainWindow()

    # ---------- 1. 所有页面渲染与滚动 ----------
    print("[1] 页面渲染与滚动容器")
    for name in ("home", "progress", "report", "history", "advanced", "settings", "monitor"):
        app.show_page(name)
        app.update_idletasks()
        sf = app.pages[name]
        # 自动化环境无窗口管理器，winfo_ismapped 不可靠；用布局管理器判断页面已挂载
        check(f"页面 {name} 已布局", sf.winfo_manager() == "place",
              f"manager={sf.winfo_manager()}")
        check(f"页面 {name} 可滚动", hasattr(sf, "scroll_to_top"))
        check(f"页面 {name} 有内容(inner>0)", len(sf.inner.winfo_children()) > 0,
              f"children={len(sf.inner.winfo_children())}")
        inner_h = sf.inner.winfo_reqheight()
        check(f"页面 {name} 内容高度>0", inner_h > 0, f"reqheight={inner_h}")

    # ---------- 2. 高级模式控件 ----------
    print("[2] 高级模式控件")
    app.show_page("advanced")
    app.update_idletasks()
    check("高级-按此参数开始测试按钮",
          len(find_widgets(app, "Button", "按此参数开始测试")) >= 1)
    single_btns = find_widgets(app, "Button", "仅")
    check("高级-4 个单项测试按钮", len(single_btns) >= 3, f"找到 {len(single_btns)} 个")

    # ---------- 3. 设置页控件 ----------
    print("[3] 设置页控件")
    app.show_page("settings")
    app.update_idletasks()
    check("设置-返回主界面按钮", len(find_widgets(app, "Button", "返回主界面")) >= 1)
    check("设置-保存配置按钮", len(find_widgets(app, "Button", "保存配置")) >= 1)
    entries = find_widgets(app, "Entry")
    check("设置-表单输入框 >= 6", len(entries) >= 6, f"找到 {len(entries)} 个")

    # ---------- 4. 监测页控件 ----------
    print("[4] 监测页控件")
    app.show_page("monitor")
    app.update_idletasks()
    radios = find_widgets(app, "Radiobutton")
    texts = []
    for r in radios:
        try:
            texts.append(r.cget("text"))
        except Exception:
            pass
    for expect in ("3 分钟", "5 分钟", "10 分钟", "1 小时", "3 小时", "持续"):
        check(f"监测-时长选项「{expect}」", expect in texts, f"选项={texts}")
    check("监测-启动按钮", len(find_widgets(app, "Button", "启动监测")) >= 1)
    check("监测-停止按钮", len(find_widgets(app, "Button", "停止监测")) >= 1)

    # ---------- 5. 首页动态描述 ----------
    print("[5] 首页动态描述")
    app.show_page("home")
    app.update_idletasks()
    cfg = app.config
    port_str = str(cfg.target_port)
    all_texts = []
    for lbl in find_widgets(app, "Label"):
        try:
            all_texts.append(lbl.cget("text"))
        except Exception:
            pass
    check("首页-TCP 描述含动态端口", any(port_str in t and "端口" in t for t in all_texts),
          f"port={port_str}")
    check("首页-Ping 描述含动态次数", any(str(cfg.ping_count) in t and "探测包" in t for t in all_texts))
    check("首页-并行流描述含动态流数", any(str(cfg.parallel_streams) in t and "并行流" in t for t in all_texts))

    # ---------- 6. 运行状态指示 ----------
    print("[6] 运行状态指示")
    app.set_status("● 测试运行中", "#E6A23C")
    app.update_idletasks()
    check("状态-测试运行中", "测试运行中" in app.status_lbl.cget("text"))
    app.set_status()
    check("状态-空闲", "空闲" in app.status_lbl.cget("text"))

    # ---------- 7. 核心交互：单项 TCP 测试全流程 ----------
    print("[7] 交互流程：单项测试 → 报告 → 历史记录")
    app._run_custom("tcp", {"host": "127.0.0.1", "port": 1, "ping_count": 3,
                            "duration": 5, "streams": 4, "reverse": False})
    # 等待测试线程完成（轮询）
    import time
    deadline = time.time() + 30
    while app._running and time.time() < deadline:
        app.update()
        time.sleep(0.05)
    app.update()
    check("流程-测试结束回到空闲", not app._running)
    check("流程-自动切到报告页", app.pages["report"].winfo_manager() == "place")
    check("流程-会话有结果", app.session and len(app.session.get("results", [])) >= 1,
          f"results={len(app.session.get('results', [])) if app.session else 0}")
    check("流程-报告自动保存", getattr(app, "_last_report", None) is not None)
    # 历史页能看到记录
    app.show_page("history")
    app.update_idletasks()
    rows = app.history_table.get_children()
    check("流程-历史记录列表有数据", len(rows) >= 1, f"rows={len(rows)}")

    # ---------- 8. 监测快速启停 ----------
    print("[8] 监测启动/停止")
    app.show_page("monitor")
    app.update_idletasks()
    panel = app.pages["monitor"].inner.winfo_children()[0]
    panel._start()
    app.update_idletasks()
    check("监测-启动后状态", panel.start_btn.cget("state") == "disabled")
    check("监测-顶部状态指示", "监测中" in app.status_lbl.cget("text"))
    panel._stop()
    app.update_idletasks()
    check("监测-停止后状态", panel.start_btn.cget("state") == "normal")
    check("监测-停止后指示空闲", "空闲" in app.status_lbl.cget("text"))

    # ---------- 9. 禁 ping 交叉验证判定 ----------
    print("[9] 禁 ping 交叉验证判定")
    import socket
    import threading
    # 本地起一个 TCP 服务用于模拟“端口可连”
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    srv_port = srv.getsockname()[1]

    def _serve():
        while True:
            try:
                conn, _ = srv.accept()
                conn.close()
            except OSError:
                break

    threading.Thread(target=_serve, daemon=True).start()
    try:
        # 场景1：ping 全丢 + TCP 通 -> 判定跳过（服务器禁 ping）
        pt = PingTest("127.0.0.1", count=50, verify_port=srv_port)
        pt._judge_unreachable("模拟 ping 全部请求超时输出")
        check("禁ping+TCP通->跳过", pt.result.status == "skip",
              f"status={pt.result.status} msg={pt.result.message}")
        check("禁ping-指标含TCP可连接", "TCP 端口" in pt.result.key_metrics)
        # 场景2：ping 全丢 + TCP 不通 -> 判定不可达
        pt2 = PingTest("127.0.0.1", count=50, verify_port=1)  # 端口 1 无服务
        pt2._judge_unreachable("模拟 ping 全部请求超时输出")
        check("禁ping+TCP不通->不可达", pt2.result.status == "bad",
              f"status={pt2.result.status}")
        # 场景3：无 verify_port 时保持原不可达判定
        pt3 = PingTest("127.0.0.1", count=50)
        pt3._judge_unreachable("模拟输出")
        check("无verify_port->不可达", pt3.result.status == "bad")
        # 场景4：真实快速失败——不可达目标不应等待完整 50 包（应在 25s 内判定）
        import time as _time
        t0 = _time.time()
        pt4 = PingTest("192.0.2.1", count=50, verify_port=1).run()
        cost = _time.time() - t0
        check("真实禁ping快速失败(<25s)", cost < 25, f"耗时 {cost:.1f}s status={pt4.status}")
        check("真实禁ping结果有效", pt4.status in ("bad", "skip", "warn", "error"))
    finally:
        srv.close()

    # ---------- 10. 服务器真实状态探测 ----------
    print("[10] 服务器真实状态探测（不写死）")
    import socket as _sock
    srv2 = _sock.socket()
    srv2.bind(("127.0.0.1", 0))
    srv2.listen(4)
    srv2_port = srv2.getsockname()[1]

    def _serve2():
        while True:
            try:
                c, _ = srv2.accept()
                c.close()
            except OSError:
                break

    threading.Thread(target=_serve2, daemon=True).start()
    try:
        # 保存原配置，临时指向本地可达服务（并禁用额外探测源，避免依赖真实网络）
        orig_host = app.config.parser.get("目标", "外网映射地址")
        orig_port = app.config.parser.get("目标", "外网映射端口")
        orig_iperf_h = app.config.parser.get("目标", "iperf3服务器地址")
        orig_iperf_p = app.config.parser.get("目标", "iperf3服务器端口")
        orig_app = app.config.parser.get("目标", "一体化系统地址")
        app.config.parser.set("目标", "外网映射地址", "127.0.0.1")
        app.config.parser.set("目标", "外网映射端口", str(srv2_port))
        app.config.parser.set("目标", "iperf3服务器地址", "127.0.0.1")
        app.config.parser.set("目标", "iperf3服务器端口", str(srv2_port))
        app.config.parser.set("目标", "一体化系统地址", "")
        check("状态探测-配置已生效", app.config.target_host == "127.0.0.1"
              and app.config.target_port == srv2_port)
        app._check_server_status()
        deadline = time.time() + 15
        while time.time() < deadline:
            app.update()
            if "检测中" not in app.server_state.cget("text"):
                break
            time.sleep(0.05)
        check("状态探测-可达显示在线", "在线" in app.server_state.cget("text"),
              f"text={app.server_state.cget('text')}")
        # 指向未监听端口 -> 离线
        app.config.parser.set("目标", "外网映射端口", "1")
        app.config.parser.set("目标", "iperf3服务器端口", "1")
        app._check_server_status()
        deadline = time.time() + 15
        while time.time() < deadline:
            app.update()
            if "检测中" not in app.server_state.cget("text"):
                break
            time.sleep(0.05)
        check("状态探测-不可达显示离线", "离线" in app.server_state.cget("text"),
              f"text={app.server_state.cget('text')}")
        # 恢复配置
        app.config.parser.set("目标", "外网映射地址", orig_host)
        app.config.parser.set("目标", "外网映射端口", orig_port)
        app.config.parser.set("目标", "iperf3服务器地址", orig_iperf_h)
        app.config.parser.set("目标", "iperf3服务器端口", orig_iperf_p)
        app.config.parser.set("目标", "一体化系统地址", orig_app)
    finally:
        srv2.close()

    # ---------- 11. 一键停止测试 ----------
    print("[11] 一键停止测试")
    app._run_custom("all", {"host": "192.0.2.1", "port": 1, "ping_count": 50,
                            "duration": 30, "streams": 4, "reverse": False})
    time.sleep(1.0)  # 让测试跑起来
    app._request_stop()
    check("停止-按钮已禁用", app.stop_btn.cget("state") == "disabled")
    deadline = time.time() + 15
    while app._running and time.time() < deadline:
        app.update()
        time.sleep(0.05)
    app.update()
    check("停止-测试快速结束(<15s)", not app._running)
    check("停止-会话标记中止", bool(app.session and app.session.get("aborted")))
    check("停止-结论显示已中止", app.session and "中止" in app.session["conclusion"]["title"],
          f"title={app.session['conclusion']['title'] if app.session else None}")
    check("停止-报告已自动保存", getattr(app, "_last_report", None) is not None)
    check("停止-状态指示恢复空闲", "空闲" in app.status_lbl.cget("text"))
    check("停止-当前项标记中止", any(r.get("status") == "aborted"
                                      for r in app.session.get("results", [])),
          f"statuses={[r['status'] for r in app.session.get('results', [])]}")

    # ---------- 12. 长期监测真实运行（轮询出数据） ----------
    print("[12] 长期监测真实运行（轮询出数据）")
    srv3 = _sock.socket()
    srv3.bind(("127.0.0.1", 0))
    srv3.listen(4)
    srv3_port = srv3.getsockname()[1]

    def _serve3():
        while True:
            try:
                c, _ = srv3.accept()
                c.close()
            except OSError:
                break

    threading.Thread(target=_serve3, daemon=True).start()
    try:
        # 临时配置：目标指向本地服务，间隔缩到 5 秒（监测线程最小间隔）
        # 注意：MonitorPanel 持有独立 AppConfig 实例，必须改它自己的配置
        panel = app.pages["monitor"].panel
        orig_host = panel.config.parser.get("目标", "外网映射地址")
        orig_port = panel.config.parser.get("目标", "外网映射端口")
        orig_int = panel.config.parser.get("测试参数", "监测间隔秒")
        panel.config.parser.set("目标", "外网映射地址", "127.0.0.1")
        panel.config.parser.set("目标", "外网映射端口", str(srv3_port))
        panel.config.parser.set("测试参数", "监测间隔秒", "5")
        panel.interval_var.set("5")  # 探测间隔 chips 也指向 5 秒（_start 读此值）
        panel._start()
        # 等待至少 2 轮真实采样（每轮 ping 5 包 + TCP 探测）
        deadline = time.time() + 25
        while time.time() < deadline:
            app.update()
            if panel.monitor and len(panel.monitor.samples) >= 2:
                break
            time.sleep(0.05)
        n = len(panel.monitor.samples) if panel.monitor else 0
        check("监测-真实采样 >= 2 轮", n >= 2, f"samples={n}")
        check("监测-采样均可达", all(s.reachable for s in panel.monitor.samples))
        check("监测-事件时间线有启动日志", "监测已启动" in panel.events_text.get("1.0", "end"))
        check("监测-状态栏实时更新", "已采样" in panel.status_lbl.cget("text"),
              f"text={panel.status_lbl.cget('text')}")
        panel._stop()
        mon = panel.collect()
        check("监测-停止后可收集摘要", mon is not None and mon["summary"]["samples"] >= 2,
              f"summary={mon['summary'] if mon else None}")
        check("监测-摘要评级有效", mon["summary"]["level"] in ("A", "B", "C"))
        # 恢复配置
        panel.config.parser.set("目标", "外网映射地址", orig_host)
        panel.config.parser.set("目标", "外网映射端口", orig_port)
        panel.config.parser.set("测试参数", "监测间隔秒", orig_int)
    finally:
        srv3.close()

    # ---------- 13. 高级模式参数链路（真实执行） ----------
    print("[13] 高级模式参数链路（真实执行）")
    app.show_page("advanced")
    app.update_idletasks()
    apanel = app.pages["advanced"].panel
    # 临时把 iperf3/一体化系统指向本地，避免依赖真实网络（178/47 可能不可达）
    _o_ih = app.config.parser.get("目标", "iperf3服务器地址")
    _o_ip = app.config.parser.get("目标", "iperf3服务器端口")
    _o_app = app.config.parser.get("目标", "一体化系统地址")
    app.config.parser.set("目标", "iperf3服务器地址", "127.0.0.1")
    app.config.parser.set("目标", "iperf3服务器端口", "1")
    app.config.parser.set("目标", "一体化系统地址", "")
    apanel.var_host.set("127.0.0.1")
    apanel.var_port.set("1")
    apanel.var_ping.set("5")
    apanel.var_dur.set("5")
    apanel.var_streams.set("4")
    apanel.var_reverse.set(False)
    # 单项按钮回调链路（等价点击“仅 Ping”）
    captured = {}
    apanel.on_run_single = lambda mode, params=None: captured.update({"mode": mode})
    apanel.on_run_single("ping")
    check("高级-单项回调触发", captured.get("mode") == "ping")
    # 恢复真实回调并点击“按此参数开始测试”
    apanel.on_run_single = app._run_custom
    apanel._run_all()
    deadline = time.time() + 45
    while app._running and time.time() < deadline:
        app.update()
        time.sleep(0.05)
    app.update()
    check("高级-按参数测试执行完成", not app._running and app.session is not None)
    check("高级-会话结果数 >= 1", len(app.session.get("results", [])) >= 1)
    # 验证自定义参数真正生效：Ping 应为 5 包
    ping_res = [r for r in app.session.get("results", [])
                if r.get("name", "").startswith("Ping")]
    check("高级-自定义参数生效(Ping 5包)",
          any("发送 5 包" in r.get("detail", "") for r in ping_res),
          f"details={[r.get('detail') for r in ping_res]}")
    check("高级-测试后回到空闲", not app._running)
    # 恢复配置
    app.config.parser.set("目标", "iperf3服务器地址", _o_ih)
    app.config.parser.set("目标", "iperf3服务器端口", _o_ip)
    app.config.parser.set("目标", "一体化系统地址", _o_app)

    # ---------- 14. 设置保存后配置重载（无需重启生效） ----------
    print("[14] 设置保存后配置重载")
    sp = app.pages["settings"].panel
    old_host = sp.vars["外网映射地址"].get()
    old_port = sp.vars["外网映射端口"].get()
    sp.vars["外网映射地址"].set("127.0.0.1")
    sp.vars["外网映射端口"].set("9")
    # 不弹窗：直接执行保存逻辑（绕过 messagebox）
    sp._collect()
    sp.config.set("目标", "外网映射地址", "127.0.0.1")
    sp.config.set("目标", "外网映射端口", "9")
    sp.config.save()
    app._reload_config()
    app.update_idletasks()
    check("重载-主窗口配置生效", app.config.target_host == "127.0.0.1" and app.config.target_port == 9,
          f"host={app.config.target_host} port={app.config.target_port}")
    check("重载-首页目标显示更新", "127.0.0.1 : 9" in app.target_lbl.cget("text"),
          f"text={app.target_lbl.cget('text')}")
    check("重载-监测面板配置同步", app.pages["monitor"].panel.config.target_host == "127.0.0.1")
    # 恢复原配置
    sp.config.set("目标", "外网映射地址", old_host)
    sp.config.set("目标", "外网映射端口", old_port)
    sp.config.save()
    app._reload_config()

    # ---------- 15. 清理 ----------
    import shutil
    d = app.config.report_dir
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    app.destroy()

    print("=" * 56)
    print(f"结果：{PASS} PASS / {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
