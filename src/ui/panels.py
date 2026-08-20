# -*- coding: utf-8 -*-
"""
辅助面板：高级模式、设置、长期监测三个面板。
"""
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from . import theme
from config import AppConfig
from monitor import NetworkMonitor


class AdvancedPanel(tk.Frame):
    """高级模式：自定义参数 + 单项测试"""

    def __init__(self, master, on_run_single, **kw):
        super().__init__(master, bg=theme.BG, **kw)
        self.on_run_single = on_run_single
        self.config = AppConfig()
        self._build()

    def _build(self):
        card = tk.Frame(self, bg=theme.CARD, highlightbackground=theme.LINE,
                        highlightthickness=1)
        card.pack(fill="x", pady=6)
        tk.Label(card, text="🔧 高级模式 · 自定义测试参数", font=theme.ui_font(13, True),
                 bg=theme.CARD, fg=theme.PRIMARY).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(card, text="适合运维人员；修改后点击「按此参数开始测试」", font=theme.ui_font(9),
                 bg=theme.CARD, fg=theme.MUTED).pack(anchor="w", padx=18)

        form = tk.Frame(card, bg=theme.CARD)
        form.pack(fill="x", padx=18, pady=10)
        self.var_host = self._field(form, 0, "目标服务器", self.config.target_host)
        self.var_port = self._field(form, 1, "目标端口", str(self.config.target_port))
        self.var_ping = self._field(form, 2, "Ping 次数", str(self.config.ping_count))
        self.var_dur = self._field(form, 3, "iperf3 时长（秒）", str(self.config.iperf_duration))
        self.var_streams = self._field(form, 4, "并行流数", str(self.config.parallel_streams))
        self.var_reverse = tk.BooleanVar(value=True)
        row = tk.Frame(form, bg=theme.CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="反向测试（下行）", font=theme.ui_font(10), bg=theme.CARD,
                 width=16, anchor="w").pack(side="left")
        ttk.Checkbutton(row, variable=self.var_reverse, text="启用（测下行带宽）").pack(side="left")

        btns = tk.Frame(form, bg=theme.CARD)
        btns.pack(fill="x", pady=(12, 4))
        self.run_all_btn = tk.Button(
            btns, text="▶ 按此参数开始测试", command=self._run_all,
            font=theme.ui_font(11, True), bg=theme.PRIMARY, fg="white",
            activebackground=theme.PRIMARY_DARK, activeforeground="white",
            relief="flat", padx=24, pady=8, cursor="hand2")
        self.run_all_btn.pack(side="right")
        tk.Button(btns, text="恢复默认", font=theme.ui_font(10), bg=theme.BG,
                  fg=theme.TEXT, relief="flat", padx=16, pady=8,
                  command=self._reset).pack(side="right", padx=8)

        # 单项测试
        card2 = tk.Frame(self, bg=theme.CARD, highlightbackground=theme.LINE,
                         highlightthickness=1)
        card2.pack(fill="x", pady=6)
        tk.Label(card2, text="⚡ 运行单项测试", font=theme.ui_font(12, True),
                 bg=theme.CARD, fg=theme.PRIMARY).pack(anchor="w", padx=18, pady=(14, 6))
        row = tk.Frame(card2, bg=theme.CARD)
        row.pack(fill="x", padx=18, pady=(0, 14))
        for text, mode in (("📶 仅 Ping", "ping"), ("🔌 仅端口", "tcp"),
                           ("⬆️ 仅带宽", "iperf"), ("🗺️ 仅路由", "tracert")):
            tk.Button(row, text=text, font=theme.ui_font(10), bg=theme.ACCENT_LIGHT,
                      fg=theme.PRIMARY, relief="flat", padx=14, pady=6, cursor="hand2",
                      command=lambda m=mode: self._run_single(m)).pack(side="left", padx=4)
        tk.Label(card2, text="（单项测试使用上方表单参数，如并行流数/时长等）",
                 font=theme.ui_font(8), bg=theme.CARD, fg=theme.MUTED
                 ).pack(anchor="w", padx=18, pady=(0, 12))

    def _field(self, parent, row_idx, label, value):
        row = tk.Frame(parent, bg=theme.CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, font=theme.ui_font(10), bg=theme.CARD,
                 width=16, anchor="w").pack(side="left")
        var = tk.StringVar(value=value)
        tk.Entry(row, textvariable=var, font=theme.ui_font(10), width=22,
                 relief="solid", bd=1).pack(side="left")
        return var

    def _reset(self):
        self.config.load()
        self.var_host.set(self.config.target_host)
        self.var_port.set(str(self.config.target_port))
        self.var_ping.set(str(self.config.ping_count))
        self.var_dur.set(str(self.config.iperf_duration))
        self.var_streams.set(str(self.config.parallel_streams))

    def _run_single(self, mode):
        """单项测试：使用当前表单参数（并行流数/时长等均生效）"""
        params = self.get_params()
        self.on_run_single(mode, params if params else None)

    def _run_all(self):
        try:
            host = self.var_host.get().strip()
            port = int(self.var_port.get())
            ping = int(self.var_ping.get())
            dur = int(self.var_dur.get())
            streams = int(self.var_streams.get())
        except ValueError:
            messagebox.showerror("参数错误", "请检查参数是否为有效数字")
            return
        params = {"host": host, "port": port, "ping_count": ping,
                  "duration": dur, "streams": streams, "reverse": self.var_reverse.get()}
        self.on_run_single("all", params)

    def get_params(self) -> dict:
        try:
            return {"host": self.var_host.get().strip(), "port": int(self.var_port.get()),
                    "ping_count": int(self.var_ping.get()),
                    "duration": int(self.var_dur.get()),
                    "streams": int(self.var_streams.get()),
                    "reverse": self.var_reverse.get()}
        except ValueError:
            return {}


class SettingsPanel(tk.Frame):
    """设置：目标服务器与默认参数"""

    def __init__(self, master, on_back=None, on_saved=None, **kw):
        super().__init__(master, bg=theme.BG, **kw)
        self.config = AppConfig()
        self.on_back = on_back
        self.on_saved = on_saved
        self._build()

    def _build(self):
        card = tk.Frame(self, bg=theme.CARD, highlightbackground=theme.LINE,
                        highlightthickness=1)
        card.pack(fill="x", pady=6)
        head = tk.Frame(card, bg=theme.CARD)
        head.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(head, text="⚙️ 设置", font=theme.ui_font(13, True),
                 bg=theme.CARD, fg=theme.PRIMARY).pack(side="left")
        if self.on_back:
            tk.Button(head, text="← 返回主界面", font=theme.ui_font(9), bg=theme.BG,
                      fg=theme.PRIMARY, relief="flat", padx=12, pady=4, cursor="hand2",
                      command=self.on_back).pack(side="right")
        tk.Label(card, text="保存后将写入 config.ini，供本机所有用户使用", font=theme.ui_font(9),
                 bg=theme.CARD, fg=theme.MUTED).pack(anchor="w", padx=18)

        form = tk.Frame(card, bg=theme.CARD)
        form.pack(fill="x", padx=18, pady=10)
        self.vars = {}
        fields = [
            ("外网映射地址", self.config.target_host, "NAT 映射地址（变更时在此修改）"),
            ("外网映射端口", str(self.config.target_port), ""),
            ("iperf3服务器地址", self.config.iperf3_host, "带宽测试专用；留空默认等于外网映射地址"),
            ("iperf3服务器端口", str(self.config.iperf3_port), ""),
            ("测试源IP", self.config.source_ip, "本机多网卡时指定测试网卡 IP，留空自动"),
            ("内网真实地址", self.config.inner_host, "仅作备注参考，不参与测试"),
            ("内网真实端口", str(self.config.inner_port), ""),
            ("一体化系统地址", self.config.app_host, "需含 http:// 或 https:// 前缀，用于 HTTP/DNS 测试"),
            ("出口检测地址", self.config.egress_host, "公网目标，判断出口链路；政务网隔离公网时留空关闭"),
            ("出口检测端口", str(self.config.egress_port), ""),
            ("参考带宽(Mbps)", str(self.config.reference_bandwidth) if self.config.reference_bandwidth else "", "留空=自动评估带宽水平，不预设参考值"),
            ("报告保存目录", self.config.report_dir, "可填绝对路径或相对路径"),
            ("监测间隔(秒)", str(self.config.monitor_interval), "修改后需重新启动监测才生效"),
            ("定时检测(是/否)", "是" if self.config.sched_enabled else "否", "到设定时间自动跑快速检测并保存报告"),
            ("定时检测时间", self.config.sched_time, "格式 HH:MM，如 08:30"),
        ]
        for i, (label, value, hint) in enumerate(fields):
            row = tk.Frame(form, bg=theme.CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=theme.ui_font(10), bg=theme.CARD,
                     width=16, anchor="w").pack(side="left")
            var = tk.StringVar(value=value)
            tk.Entry(row, textvariable=var, font=theme.ui_font(10),
                     relief="solid", bd=1).pack(side="left", fill="x", expand=True)
            self.vars[label] = var
            if hint:
                tk.Label(row, text=hint, font=theme.ui_font(8), bg=theme.CARD,
                         fg=theme.MUTED).pack(side="left", padx=8)

        btns = tk.Frame(card, bg=theme.CARD)
        btns.pack(fill="x", padx=18, pady=(6, 14))
        tk.Button(btns, text="💾 保存配置", font=theme.ui_font(11, True), bg=theme.PRIMARY,
                  fg="white", relief="flat", padx=22, pady=7, cursor="hand2",
                  command=self._save).pack(side="right")
        tk.Button(btns, text="恢复默认", font=theme.ui_font(10), bg=theme.BG,
                  fg=theme.TEXT, relief="flat", padx=16, pady=7,
                  command=self._reset).pack(side="right", padx=8)

    def _collect(self) -> dict:
        data = {k: v.get().strip() for k, v in self.vars.items()}
        return data

    def _save(self):
        data = self._collect()
        try:
            self.config.set("目标", "外网映射地址", data["外网映射地址"])
            self.config.set("目标", "外网映射端口", data["外网映射端口"])
            self.config.set("目标", "iperf3服务器地址", data["iperf3服务器地址"])
            self.config.set("目标", "iperf3服务器端口", data["iperf3服务器端口"])
            self.config.set("目标", "测试源IP", data["测试源IP"])
            self.config.set("目标", "内网真实地址", data["内网真实地址"])
            self.config.set("目标", "内网真实端口", data["内网真实端口"])
            self.config.set("目标", "一体化系统地址", data["一体化系统地址"])
            self.config.set("目标", "出口检测地址", data["出口检测地址"])
            self.config.set("目标", "出口检测端口", data["出口检测端口"])
            self.config.set("目标", "参考带宽Mbps", data["参考带宽(Mbps)"])
            self.config.set("测试参数", "报告目录", data["报告保存目录"])
            self.config.set("测试参数", "监测间隔秒", data["监测间隔(秒)"])
            self.config.set("定时检测", "启用", data["定时检测(是/否)"])
            self.config.set("定时检测", "时间", data["定时检测时间"])
            if self.config.save():
                # 通知主窗口重载配置（体检/监测/状态显示立即生效）
                if self.on_saved:
                    self.on_saved()
                messagebox.showinfo("保存成功", "配置已保存到 config.ini")
            else:
                messagebox.showerror("保存失败", "无法写入配置文件，请检查目录权限")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("保存失败", str(exc))

    def _reset(self):
        self.config.load()
        self.vars["外网映射地址"].set(self.config.target_host)
        self.vars["外网映射端口"].set(str(self.config.target_port))
        self.vars["iperf3服务器地址"].set(self.config.iperf3_host)
        self.vars["iperf3服务器端口"].set(str(self.config.iperf3_port))
        self.vars["测试源IP"].set(self.config.source_ip)
        self.vars["内网真实地址"].set(self.config.inner_host)
        self.vars["内网真实端口"].set(str(self.config.inner_port))
        self.vars["一体化系统地址"].set(self.config.app_host)
        self.vars["出口检测地址"].set(self.config.egress_host)
        self.vars["出口检测端口"].set(str(self.config.egress_port))
        self.vars["参考带宽(Mbps)"].set(str(self.config.reference_bandwidth))
        self.vars["报告保存目录"].set(self.config.report_dir)
        self.vars["监测间隔(秒)"].set(str(self.config.monitor_interval))
        self.vars["定时检测(是/否)"].set("是" if self.config.sched_enabled else "否")
        self.vars["定时检测时间"].set(self.config.sched_time)


class MonitorPanel(tk.Frame):
    """长期监测：启动/停止 + 实时状态 + 事件时间线（日志性质）"""

    def __init__(self, master, on_status=None, on_report=None, **kw):
        super().__init__(master, bg=theme.BG, **kw)
        self.config = AppConfig()
        self.monitor = None
        self.stop_flag = threading.Event()
        self.on_status = on_status
        self.on_report = on_report
        self._updates = queue.Queue()   # 监测线程 -> 主线程 的更新通道
        self._rendered_events = 0       # 已写入时间线的事件数
        self._build()
        self.after(200, self._poll_updates)  # 主线程轮询监测更新

    def _build(self):
        card = tk.Frame(self, bg=theme.CARD, highlightbackground=theme.LINE,
                        highlightthickness=1)
        card.pack(fill="x", pady=6)
        tk.Label(card, text="⏱️ 长期监测 · 专治时断时续", font=theme.ui_font(13, True),
                 bg=theme.CARD, fg=theme.PRIMARY).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(card, text="周期性 Ping + 端口探测，自动捕获丢包 / 断连 / 延迟突增事件",
                 font=theme.ui_font(9), bg=theme.CARD, fg=theme.MUTED).pack(anchor="w", padx=18)

        row = tk.Frame(card, bg=theme.CARD)
        row.pack(fill="x", padx=18, pady=10)
        tk.Label(row, text="检测时长", font=theme.ui_font(10), bg=theme.CARD).pack(side="left")
        self.dur_var = tk.StringVar(value="10")
        for text, val in (("3 分钟", "3"), ("5 分钟", "5"), ("10 分钟", "10"),
                          ("1 小时", "60"), ("3 小时", "180"), ("持续", "0")):
            tk.Radiobutton(row, text=text, variable=self.dur_var, value=val,
                           font=theme.ui_font(10), bg=theme.CARD,
                           selectcolor=theme.CARD).pack(side="left", padx=6)
        tk.Label(row, text="（检测时长 = 总时长，到时自动停止并出报告）", font=theme.ui_font(8),
                 bg=theme.CARD, fg=theme.MUTED).pack(side="left", padx=8)

        # 探测间隔（采样率）
        row1b = tk.Frame(card, bg=theme.CARD)
        row1b.pack(fill="x", padx=18, pady=(0, 8))
        tk.Label(row1b, text="探测间隔", font=theme.ui_font(10), bg=theme.CARD).pack(side="left")
        self.interval_var = tk.StringVar(value=str(self.config.monitor_interval))
        for text, val in (("30 秒", "30"), ("1 分钟", "60"), ("5 分钟", "300")):
            tk.Radiobutton(row1b, text=text, variable=self.interval_var, value=val,
                           font=theme.ui_font(10), bg=theme.CARD,
                           selectcolor=theme.CARD).pack(side="left", padx=6)
        tk.Label(row1b, text="（采样间隔 = 每隔多久测一轮，趋势图按此间隔划分）", font=theme.ui_font(8),
                 bg=theme.CARD, fg=theme.MUTED).pack(side="left", padx=8)

        row2 = tk.Frame(card, bg=theme.CARD)
        row2.pack(fill="x", padx=18, pady=(0, 8))
        self.start_btn = tk.Button(row2, text="▶ 启动监测", font=theme.ui_font(11, True),
                                   bg=theme.PRIMARY, fg="white", relief="flat",
                                   padx=22, pady=7, cursor="hand2", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(row2, text="⏹ 停止监测", font=theme.ui_font(11, True),
                                  bg=theme.DANGER, fg="white", relief="flat",
                                  padx=22, pady=7, state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", padx=8)
        self.status_lbl = tk.Label(row2, text="未启动", font=theme.ui_font(10, True),
                                   bg=theme.CARD, fg=theme.MUTED)
        self.status_lbl.pack(side="left", padx=10)

        # 运行信息：开始时间 / 已运行 / 剩余
        row3 = tk.Frame(card, bg=theme.CARD)
        row3.pack(fill="x", padx=18, pady=(0, 10))
        self.time_lbl = tk.Label(row3, text="开始时间：—    已运行：—    剩余：—",
                                 font=theme.ui_font(9), bg=theme.CARD, fg=theme.MUTED)
        self.time_lbl.pack(side="left")

        # 状态区
        card2 = tk.Frame(self, bg=theme.CARD, highlightbackground=theme.LINE,
                         highlightthickness=1)
        card2.pack(fill="both", expand=True, pady=6)
        tk.Label(card2, text="🚨 不稳定事件时间线", font=theme.ui_font(12, True),
                 bg=theme.CARD, fg=theme.PRIMARY).pack(anchor="w", padx=18, pady=(12, 4))
        self.events_text = tk.Text(card2, height=14, font=theme.ui_font(10),
                                   bg=theme.BG, relief="flat", padx=10, pady=8,
                                   state="disabled")
        self.events_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        # 时间线日志着色：bad=红 warn=橙 info=灰
        self.events_text.tag_configure("bad", foreground=theme.DANGER, font=theme.ui_font(10, True))
        self.events_text.tag_configure("warn", foreground="#B06A12")
        self.events_text.tag_configure("info", foreground=theme.MUTED)
        self.events_text.tag_configure("ok", foreground=theme.SUCCESS)

    def _start(self):
        host, port = self.config.target_host, self.config.target_port
        dur_min = int(self.dur_var.get())
        interval = int(self.interval_var.get())
        # 探测间隔同步写入配置（采样率）
        self.config.set("测试参数", "监测间隔秒", str(interval))
        self.stop_flag.clear()
        self.monitor = NetworkMonitor(
            host, port, interval=interval,
            duration=(dur_min * 60 if dur_min else None),
            progress_cb=self._on_progress, stop_event=self.stop_flag,
            http_url=self.config.app_host)
        self.monitor.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_lbl.config(text="监测运行中…", fg=theme.SUCCESS)
        self.start_ts = time.time()
        self.stop_ts = None
        self.dur_seconds = dur_min * 60 if dur_min else None
        self._update_time_info()
        if self.on_status:
            self.on_status("● 监测中", theme.ACCENT)
        self._log(f"▶ 监测已启动：目标 {host}:{port}，间隔 {interval}s"
                  f"{'，时长 ' + str(dur_min) + ' 分钟' if dur_min else '，持续监测'}\n")

    def _update_time_info(self):
        """更新开始时间 / 已运行 / 剩余时间显示（停止后冻结，不再增长）"""
        if not getattr(self, "start_ts", None):
            self.time_lbl.config(text="开始时间：—    已运行：—    剩余：—")
            return
        start_str = time.strftime("%H:%M:%S", time.localtime(self.start_ts))
        if getattr(self, "stop_ts", None):
            # 已停止：固定显示停止时的时长
            elapsed = self.stop_ts - self.start_ts
            run_str = self._fmt_duration(elapsed)
            self.time_lbl.config(
                text=f"开始时间：{start_str}    已运行：{run_str}    状态：已结束")
            return
        elapsed = time.time() - self.start_ts
        run_str = self._fmt_duration(elapsed)
        if self.dur_seconds:
            remain = max(0, self.dur_seconds - elapsed)
            remain_str = self._fmt_duration(remain)
        else:
            remain_str = "持续监测"
        self.time_lbl.config(
            text=f"开始时间：{start_str}    已运行：{run_str}    剩余：{remain_str}")

    @staticmethod
    def _fmt_duration(secs: float) -> str:
        secs = int(secs)
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}小时{m}分{s}秒"
        if m:
            return f"{m}分{s}秒"
        return f"{s}秒"

    def _stop(self):
        self.stop_flag.set()
        self.stop_ts = time.time()  # 冻结运行时间显示
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_lbl.config(text="已停止", fg=theme.MUTED)
        if self.on_status:
            self.on_status("● 空闲", theme.MUTED)
        # 有采样数据则生成监测报告（含不稳定事件时间线）
        if self.monitor and self.monitor.samples:
            self._log("⏹ 监测已停止，正在生成报告…\n", "info")
            if self.on_report:
                self.after(100, self.on_report)

    def _on_progress(self, samples, events):
        # 监测线程回调：只入队，UI 更新由主线程轮询执行（tkinter 线程安全）
        self._updates.put((samples, events))

    def _poll_updates(self):
        """主线程轮询：消费监测更新队列并渲染"""
        try:
            while True:
                samples, events = self._updates.get_nowait()
                self._render(samples, events)
        except queue.Empty:
            pass
        self._update_time_info()
        self._check_monitor_finished()
        self.after(200, self._poll_updates)

    def _check_monitor_finished(self):
        """检测监测线程结束：区分『到时自动停止』与『异常终止』，恢复 UI 并尝试出报告"""
        if not (self.monitor and not self.monitor.is_alive()
                and self.start_btn.cget("state") == "disabled"):
            return
        self.stop_ts = time.time()  # 冻结运行时间显示
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.on_status:
            self.on_status("● 空闲", theme.MUTED)
        elapsed = self.stop_ts - self.start_ts
        reached = self.dur_seconds and elapsed >= self.dur_seconds - 3
        if reached:
            # 到时自动停止（正常流程）
            self.status_lbl.config(text="监测已结束（到时自动停止）", fg=theme.SUCCESS)
            self._log("⏹ 检测时长已到，监测自动停止，正在生成报告…\n", "ok")
        else:
            # 异常终止：线程提前退出（如探测异常/解析错误），不应静默
            reason = "持续监测" if not self.dur_seconds else self._fmt_duration(self.dur_seconds)
            self.status_lbl.config(text="监测异常终止（线程提前退出）", fg=theme.DANGER)
            self._log(f"⚠️ 监测异常终止：运行 {self._fmt_duration(elapsed)}，"
                      f"未到设定时长（{reason}）。已尝试生成部分结果报告。\n", "warn")
        if self.on_report and self.monitor.samples:
            self.after(100, self.on_report)

    def _render(self, samples, events):
        total = len(samples)
        bad = sum(1 for s in samples if s.loss_pct > 0 or not s.tcp_ok)
        rate = round(bad / total * 100, 1) if total else 0
        self.status_lbl.config(text=f"已采样 {total} 次 · 异常 {rate}% · 事件 {len(events)} 个",
                               fg=theme.SUCCESS if rate < 10 else theme.WARNING)
        # 追加新事件到时间线（日志性质，带颜色）
        for ev in events[self._rendered_events:]:
            tag = "bad" if ev.level == "bad" else "warn"
            lv = "严重" if ev.level == "bad" else "中等"
            self._log(f"[{ev.time_str}] {ev.type}（{lv}）：{ev.detail}\n", tag)
        self._rendered_events = len(events)

    def _log(self, text, tag="info"):
        self.events_text.config(state="normal")
        self.events_text.insert("end", text, tag)
        self.events_text.see("end")
        self.events_text.config(state="disabled")

    def collect(self) -> dict:
        """供报告使用：返回 (summary, events) 或 None"""
        if not self.monitor or not self.monitor.samples:
            return None
        summary = self.monitor.summary()
        events = [{"time_str": e.time_str, "type": e.type, "level": e.level,
                   "detail": e.detail} for e in self.monitor.events]
        return {"summary": summary, "events": events}
