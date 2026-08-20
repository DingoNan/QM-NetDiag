# -*- coding: utf-8 -*-
"""
主窗口：顶部横幅 + 内容区（体检/进度/报告/高级/设置/监测）+ 底部导航。
测试在后台线程执行，通过队列轮询刷新界面，保证界面不卡顿。
"""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

from . import theme
from .widgets import ScrollableFrame
from .panels import AdvancedPanel, SettingsPanel, MonitorPanel
import platform_info
from config import AppConfig, report_type_name, asset_path
from core import (PingTest, TcpProbeTest, Iperf3Test, TracerouteTest,
                  DnsResolveTest, HttpProbeTest, EgressProbeTest)
from core.base_test import TestResult, STATUS_SKIP
from report import build_wechat_summary, build_html_report, evaluate_session, save_report


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("网络自检工具 v1.0")
        self.geometry("960x680")
        self.minsize(820, 600)
        self.configure(bg=theme.BG)
        # 窗口图标（政务蓝信号图标）
        try:
            self.iconbitmap(asset_path("netdiag_icon.ico"))
        except Exception:  # noqa: BLE001 - 图标缺失不影响使用
            pass

        self.config = AppConfig()
        self.sys_info = platform_info.get_system_info()
        self.session = None          # 最近一次测试会话
        self._msg_queue = queue.Queue()
        self._running = False
        self._stop_flag = threading.Event()  # 一键停止测试信号
        self._current_report_type = "quick"  # 当前会话报告类型
        self._current_report_subtype = ""    # 当前会话报告子类型（如 仅带宽/3分钟）

        self._build_header()
        self._build_nav()
        self._build_pages()
        self.after(120, self._poll_queue)
        self.after(400, self._check_platform)
        self.after(900, self._check_server_status)  # 启动后真实探测目标服务器
        self.after(600, self._check_stale)
        self._sched_last = ""
        self.after(15000, self._sched_tick)  # 定时自动检测轮询

    # ---------- 界面构建 ----------
    def _build_header(self):
        header = tk.Frame(self, bg=theme.PRIMARY)
        header.pack(fill="x")
        # 顶部 Logo（政务蓝信号图标）
        try:
            self._logo_img = tk.PhotoImage(file=asset_path("netdiag_icon_48.png"))
            tk.Label(header, image=self._logo_img, bg=theme.PRIMARY
                     ).pack(side="left", padx=(18, 6), pady=8)
        except Exception:  # noqa: BLE001
            tk.Label(header, text="▣", font=theme.ui_font(16), bg=theme.PRIMARY,
                     fg="white").pack(side="left", padx=(20, 6), pady=12)
        tk.Label(header, text="网络自检工具", font=theme.ui_font(16, True),
                 bg=theme.PRIMARY, fg="white").pack(side="left", pady=12)
        tk.Label(header, text="国产化信创 · 一体化系统网络体检  v1.0 ｜ 设计：浅木·先生",
                 font=theme.ui_font(9), bg=theme.PRIMARY, fg="#C9DDF0"
                 ).pack(side="left", padx=2, pady=12)
        # 运行状态指示（位于设置按钮右侧；运行中点击可回到测试进度页）
        self.status_lbl = tk.Label(header, text="● 空闲", font=theme.ui_font(10, True),
                                   bg=theme.PRIMARY_DARK, fg=theme.MUTED,
                                   padx=12, pady=4, cursor="hand2")
        self.status_lbl.pack(side="right", padx=6)
        self.status_lbl.bind("<Button-1>", lambda e: self._goto_progress_if_running())
        tk.Button(header, text="⚙️ 设置", font=theme.ui_font(10), bg=theme.PRIMARY_DARK,
                  fg="white", relief="flat", padx=14, pady=4, cursor="hand2",
                  command=lambda: self.show_page("settings")).pack(side="right", padx=10)

    def set_status(self, text="● 空闲", color=None):
        """更新顶部运行状态指示（测试/监测运行时调用）"""
        self.status_lbl.config(text=text, fg=color or theme.MUTED)

    def _build_pages(self):
        self.container = tk.Frame(self, bg=theme.BG)
        self.container.pack(fill="both", expand=True)
        self.pages = {}
        self.pages["home"] = self._build_home()
        self.pages["progress"] = self._build_progress()
        self.pages["report"] = self._build_report()
        self.pages["history"] = self._build_history()
        self.pages["advanced"] = self._wrap_panel(
            lambda inner: AdvancedPanel(
                inner, on_run_single=lambda mode, params=None:
                self._run_custom(mode, params, report_type="advanced")))
        self.pages["settings"] = self._wrap_panel(
            lambda inner: SettingsPanel(inner, on_back=lambda: self.show_page("home"),
                                        on_saved=self._reload_config))
        self.pages["monitor"] = self._wrap_panel(
            lambda inner: MonitorPanel(inner, on_status=self.set_status,
                                       on_report=self._generate_monitor_report))
        for page in self.pages.values():
            page.place(relwidth=1, relheight=1)
        self.show_page("home")

    def _wrap_panel(self, builder):
        """把独立面板包进可滚动容器（高级/设置/监测页）
        注意：面板必须以 sf.inner 为 master 构造（pack(in_=) 不会重新父化）"""
        sf = ScrollableFrame(self.container, bg=theme.BG)
        panel = builder(sf.inner)
        panel.pack(fill="x", anchor="n", pady=(0, 16))
        sf.panel = panel  # 供外部访问内部面板（如 collect 监测结果）
        return sf

    def _refresh_target_meta(self):
        """刷新首页目标信息显示（外网映射 + iperf3 服务器）"""
        if not hasattr(self, "target_lbl"):
            return
        self.target_lbl.config(
            text=f"{self.config.target_host} : {self.config.target_port}")
        if hasattr(self, "iperf_lbl"):
            ih, ip = self.config.iperf3_host, self.config.iperf3_port
            if ih != self.config.target_host or ip != self.config.target_port:
                self.iperf_lbl.config(
                    text=f"iperf3 服务器：{ih}:{ip}（带宽测试专用）")
            else:
                self.iperf_lbl.config(text="")

    def _reload_config(self):
        """设置保存后：重载全部配置实例并刷新界面（无需重启）"""
        self.config.load()
        for key in ("advanced", "settings", "monitor"):
            panel = getattr(self.pages.get(key), "panel", None)
            if panel is not None and hasattr(panel, "config"):
                panel.config.load()
        self._refresh_target_meta()
        self._check_server_status()  # 目标可能变更，重新探测

    def _card(self, parent):
        return tk.Frame(parent, bg=theme.CARD, highlightbackground=theme.LINE,
                        highlightthickness=1)

    def _build_home(self):
        sf = ScrollableFrame(self.container, bg=theme.BG)
        page = sf.inner
        # 目标卡片
        card = self._card(page)
        card.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(card, text="🖥️", font=theme.ui_font(22)).pack(side="left", padx=14, pady=12)
        info = tk.Frame(card, bg=theme.CARD)
        info.pack(side="left", fill="x", expand=True, pady=12)
        self.target_lbl = tk.Label(info, text=f"{self.config.target_host} : {self.config.target_port}",
                                   font=theme.ui_font(15, True), bg=theme.CARD, fg=theme.TEXT)
        self.target_lbl.pack(anchor="w")
        # iperf3 服务器（可与映射目标不同）
        self.iperf_lbl = tk.Label(info, font=theme.ui_font(9), bg=theme.CARD, fg=theme.MUTED)
        self.iperf_lbl.pack(anchor="w")
        self._refresh_target_meta()
        tk.Label(info, text=f"NAT 映射 → 内网 {self.config.inner_host}:{self.config.inner_port}"
                            "（iperf3 服务端）", font=theme.ui_font(9), bg=theme.CARD,
                 fg=theme.MUTED).pack(anchor="w")
        # 服务器真实状态（启动时自动探测，不写死；多目标：映射端口 + iperf3 + 一体化系统）
        self.server_state = tk.Label(card, text="⋯ 检测中", font=theme.ui_font(10, True),
                                     bg=theme.CARD, fg=theme.MUTED, justify="left", anchor="w")
        self.server_state.pack(side="left", padx=10)
        tk.Button(card, text="检测连接", font=theme.ui_font(9), bg=theme.PRIMARY_LIGHT,
                  fg=theme.PRIMARY, relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._check_server_status).pack(side="left", padx=4)
        tk.Button(card, text="修改目标", font=theme.ui_font(9), bg=theme.PRIMARY_LIGHT,
                  fg=theme.PRIMARY, relief="flat", padx=12, pady=5, cursor="hand2",
                  command=lambda: self.show_page("settings")).pack(side="left", padx=4)

        # 主按钮
        center = tk.Frame(page, bg=theme.BG)
        center.pack(fill="x", pady=(20, 4))
        self.hero_btn = tk.Button(
            center, text="▶  开始检测", font=theme.ui_font(16, True), bg=theme.PRIMARY,
            fg="white", activebackground=theme.PRIMARY_DARK, activeforeground="white",
            relief="flat", padx=56, pady=18, cursor="hand2", command=self._on_hero_click)
        self.hero_btn.pack()
        self.hero_hint_lbl = tk.Label(center, text="点击后自动完成全部检测项 · 约需 3 分钟 · 全程无需操作",
                                      font=theme.ui_font(9), bg=theme.BG, fg=theme.MUTED)
        self.hero_hint_lbl.pack(pady=(8, 0))

        # 测试项列表
        card2 = self._card(page)
        card2.pack(fill="x", padx=20, pady=(14, 6))
        tk.Label(card2, text="📋 本次体检包含的测试项目", font=theme.ui_font(12, True),
                 bg=theme.CARD, fg=theme.TEXT).pack(anchor="w", padx=16, pady=(12, 6))
        items = [
            ("📶", "Ping 连通性测试", f"向目标发送 {self.config.ping_count} 个探测包，统计丢包率与延迟"),
            ("🔌", "TCP 端口探测", f"检测 {self.config.target_port} 端口是否可建立连接"),
            ("⬆️", "带宽测试 · 单流上行", f"iperf3 单连接 {self.config.iperf_duration} 秒，测上行吞吐"),
            ("⬆️⬆️", f"带宽测试 · {self.config.parallel_streams} 并行流", "模拟多人并发，测极限吞吐"),
            ("⬇️", "带宽测试 · 反向（下行）", "服务器向本机传输，测下行带宽与重传率"),
            ("🗺️", "路由追踪 Tracert", "逐跳定位网络路径上的故障节点"),
        ]
        for icon, name, desc in items:
            row = tk.Frame(card2, bg=theme.BG, highlightbackground=theme.LINE,
                           highlightthickness=1)
            row.pack(fill="x", padx=16, pady=3)
            tk.Label(row, text=icon, font=theme.ui_font(14), bg=theme.BG,
                     padx=8, pady=6).pack(side="left")
            col = tk.Frame(row, bg=theme.BG)
            col.pack(side="left", pady=6)
            tk.Label(col, text=name, font=theme.ui_font(10, True), bg=theme.BG,
                     fg=theme.TEXT).pack(anchor="w")
            tk.Label(col, text=desc, font=theme.ui_font(8), bg=theme.BG,
                     fg=theme.MUTED).pack(anchor="w")
        return sf

    def _build_progress(self):
        sf = ScrollableFrame(self.container, bg=theme.BG)
        page = sf.inner
        card = self._card(page)
        card.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(card, text="🧪 正在检测 · 请勿关闭窗口或断开网络", font=theme.ui_font(13, True),
                 bg=theme.CARD, fg=theme.PRIMARY).pack(anchor="w", padx=18, pady=(14, 10))
        self.progress_bar = ttk.Progressbar(card, mode="determinate", maximum=100)
        self.progress_bar.pack(fill="x", padx=18)
        self.progress_lbl = tk.Label(card, text="准备中…", font=theme.ui_font(10),
                                     bg=theme.CARD, fg=theme.MUTED)
        self.progress_lbl.pack(anchor="w", padx=18, pady=(6, 6))
        # 一键停止测试
        self.stop_btn = tk.Button(card, text="⏹ 停止测试", font=theme.ui_font(10, True),
                                  bg=theme.DANGER, fg="white", relief="flat",
                                  padx=20, pady=7, cursor="hand2", state="disabled",
                                  command=self._request_stop)
        self.stop_btn.pack(anchor="e", padx=18, pady=(0, 12))

        self.progress_items = tk.Frame(card, bg=theme.CARD)
        self.progress_items.pack(fill="x", padx=18, pady=(0, 16))
        return sf

    def _build_report(self):
        sf = ScrollableFrame(self.container, bg=theme.BG)
        page = sf.inner
        # 结论横幅
        self.banner = tk.Frame(page, bg=theme.SUCCESS_LIGHT)
        self.banner.pack(fill="x", padx=20, pady=(16, 6))
        self.banner_icon = tk.Label(self.banner, text="🟢", font=theme.ui_font(24),
                                    bg=theme.SUCCESS_LIGHT)
        self.banner_icon.pack(side="left", padx=(18, 10), pady=12)
        self.banner_title = tk.Label(self.banner, text="", font=theme.ui_font(15, True),
                                     bg=theme.SUCCESS_LIGHT, fg=theme.SUCCESS)
        self.banner_title.pack(anchor="w", pady=(10, 0))
        self.banner_desc = tk.Label(self.banner, text="", font=theme.ui_font(9),
                                    bg=theme.SUCCESS_LIGHT, fg=theme.SUCCESS, justify="left",
                                    wraplength=820)
        self.banner_desc.pack(anchor="w", pady=(0, 10))

        # 自动保存提示条
        self.report_hint = tk.Label(page, text="", font=theme.ui_font(9), bg=theme.BG,
                                    fg=theme.MUTED, justify="left", wraplength=880, anchor="w")
        self.report_hint.pack(fill="x", padx=24, pady=(0, 2))

        # 指标区
        card = self._card(page)
        card.pack(fill="x", padx=20, pady=8)
        tk.Label(card, text="📊 核心指标", font=theme.ui_font(12, True),
                 bg=theme.CARD, fg=theme.TEXT).pack(anchor="w", padx=16, pady=(12, 6))
        self.metrics_frame = tk.Frame(card, bg=theme.CARD)
        self.metrics_frame.pack(fill="x", padx=16, pady=(0, 14))

        # 明细表
        card2 = self._card(page)
        card2.pack(fill="x", padx=20, pady=8)
        tk.Label(card2, text="📋 测试明细", font=theme.ui_font(12, True),
                 bg=theme.CARD, fg=theme.TEXT).pack(anchor="w", padx=16, pady=(12, 6))
        self.report_table = ttk.Treeview(card2, columns=("item", "detail", "status"),
                                         show="headings", height=7)
        self.report_table.heading("item", text="测试项")
        self.report_table.heading("detail", text="结果摘要")
        self.report_table.heading("status", text="状态")
        self.report_table.column("item", width=190, anchor="w")
        self.report_table.column("detail", width=520, anchor="w")
        self.report_table.column("status", width=90, anchor="center")
        self.report_table.pack(fill="x", padx=16, pady=(0, 14))

        # 操作栏
        bar = tk.Frame(page, bg=theme.BG)
        bar.pack(fill="x", padx=20, pady=(6, 16))
        for text, cmd in (("📋 复制摘要（微信直发运维）", self._copy_summary),
                          ("💾 保存 HTML 报告", self._save_html),
                          ("🌐 浏览器打开", self._open_browser)):
            tk.Button(bar, text=text, font=theme.ui_font(10, True), bg=theme.PRIMARY,
                      fg="white", relief="flat", padx=16, pady=8, cursor="hand2",
                      command=cmd).pack(side="left", padx=6)
        tk.Button(bar, text="↻ 重新体检", font=theme.ui_font(10), bg=theme.BG,
                  fg=theme.PRIMARY, relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self._start_default).pack(side="left", padx=6)
        return sf

    def _build_nav(self):
        nav = tk.Frame(self, bg="white", highlightbackground=theme.LINE,
                       highlightthickness=1)
        nav.pack(fill="x", side="bottom")
        self.nav_btns = {}
        for key, text in (("home", "🏠 快速检测"), ("advanced", "🔧 高级探测"),
                          ("monitor", "⏱️ 长期监测"), ("history", "🗂️ 历史报告")):
            btn = tk.Button(nav, text=text, font=theme.ui_font(10),
                            bg="white", fg=theme.MUTED, relief="flat",
                            padx=30, pady=8, cursor="hand2",
                            command=lambda k=key: self._on_nav_click(k))
            btn.pack(side="left", expand=True, fill="x", padx=2, pady=6)
            self.nav_btns[key] = btn

    # ---------- 页面切换 ----------
    def _goto_progress_if_running(self):
        """运行中点击顶部状态指示/首页按钮：回到测试进度页"""
        if self._running:
            self.show_page("progress")

    def _on_hero_click(self):
        """首页主按钮：运行中点击查看进度，空闲时开始检测"""
        if self._running:
            self.show_page("progress")
        else:
            self._start_default()

    def _on_nav_click(self, key):
        """底部导航：测试运行中点击“快速检测”回到进度页，其余正常切换"""
        if key == "home" and self._running:
            self.show_page("progress")
        else:
            self.show_page(key)

    def show_page(self, name):
        for key, page in self.pages.items():
            page.place_forget()
        page = self.pages[name]
        page.place(relwidth=1, relheight=1)
        if hasattr(page, "scroll_to_top"):
            page.scroll_to_top()
        for key, btn in self.nav_btns.items():
            # 测试报告页属于体检流程，高亮“快速体检”；历史报告页独立高亮
            active = (key == name) or (key == "home" and name == "report")
            btn.config(bg=theme.PRIMARY_LIGHT if active else "white",
                       fg=theme.PRIMARY if active else theme.MUTED)
        if name == "history":
            self._refresh_history()

    # ---------- 历史报告页 ----------
    def _build_history(self):
        sf = ScrollableFrame(self.container, bg=theme.BG)
        page = sf.inner
        card = self._card(page)
        card.pack(fill="x", padx=20, pady=(16, 6))
        head = tk.Frame(card, bg=theme.CARD)
        head.pack(fill="x", padx=18, pady=(12, 8))
        tk.Label(head, text="🗂️ 历史报告", font=theme.ui_font(13, True), bg=theme.CARD,
                 fg=theme.PRIMARY).pack(side="left")
        tk.Label(head, text="测试完成后自动保存在报告目录，双击记录可打开", font=theme.ui_font(9),
                 bg=theme.CARD, fg=theme.MUTED).pack(side="left", padx=12)
        tk.Button(head, text="📂 打开目录", font=theme.ui_font(9), bg=theme.BG,
                  fg=theme.PRIMARY, relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._open_report_dir).pack(side="right")
        tk.Button(head, text="🔄 刷新", font=theme.ui_font(9), bg=theme.BG,
                  fg=theme.PRIMARY, relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._refresh_history).pack(side="right", padx=8)

        self.history_table = ttk.Treeview(
            page, columns=("rtype", "name", "time", "kinds", "dir"), show="headings", height=12)
        self.history_table.heading("rtype", text="报告类型")
        self.history_table.heading("name", text="报告文件")
        self.history_table.heading("time", text="测试时间")
        self.history_table.heading("kinds", text="文件格式")
        self.history_table.heading("dir", text="保存目录")
        self.history_table.column("rtype", width=90, anchor="center")
        self.history_table.column("name", width=250, anchor="w")
        self.history_table.column("time", width=130, anchor="w")
        self.history_table.column("kinds", width=80, anchor="center")
        self.history_table.column("dir", width=340, anchor="w")
        self.history_table.pack(fill="x", padx=20, pady=8)
        self.history_table.bind("<Double-1>", lambda e: self._open_history(".html"))

        bar = tk.Frame(page, bg=theme.BG)
        bar.pack(fill="x", padx=20, pady=(0, 16))
        tk.Button(bar, text="🌐 打开 HTML 报告", font=theme.ui_font(10, True), bg=theme.PRIMARY,
                  fg="white", relief="flat", padx=16, pady=8, cursor="hand2",
                  command=lambda: self._open_history(".html")).pack(side="left", padx=6)
        tk.Button(bar, text="📄 打开 TXT 日志", font=theme.ui_font(10), bg=theme.ACCENT_LIGHT,
                  fg=theme.PRIMARY, relief="flat", padx=16, pady=8, cursor="hand2",
                  command=lambda: self._open_history(".txt")).pack(side="left", padx=6)
        tk.Button(bar, text="🗑 删除所选", font=theme.ui_font(10), bg=theme.DANGER_LIGHT,
                  fg=theme.DANGER, relief="flat", padx=16, pady=8, cursor="hand2",
                  command=self._delete_history).pack(side="left", padx=6)
        self.history_hint = tk.Label(page, text="", font=theme.ui_font(9), bg=theme.BG,
                                     fg=theme.MUTED, anchor="w")
        self.history_hint.pack(fill="x", padx=24, pady=(0, 10))
        return sf

    def _refresh_history(self):
        for item in self.history_table.get_children():
            self.history_table.delete(item)
        d = self.config.report_dir
        if not os.path.isdir(d):
            self.history_hint.config(text="报告目录尚不存在，完成一次测试后会自动创建并保存")
            return
        bases = {f.rsplit(".", 1)[0] for f in os.listdir(d)
                 if f.startswith("网络测试报告_") and f.endswith((".html", ".txt"))}
        if not bases:
            self.history_hint.config(text="暂无历史报告，完成测试后会自动保存到这里")
            return
        # 排序：按测试时间（文件名时间戳）倒序，同时间按报告类型（快速→高级→长期）
        def sort_key(base):
            parts = os.path.basename(base).split("_")
            ts = (parts[-2] + parts[-1]) if len(parts) >= 4 else ""
            rtype = parts[1] if len(parts) > 1 else "未知"
            rank = {"快速检测": 0, "高级探测": 1, "长期监测": 2}.get(rtype, 9)
            return (ts, -rank)

        bases = sorted(bases, key=sort_key, reverse=True)
        for base in bases:
            html_p = os.path.join(d, base + ".html")
            txt_p = os.path.join(d, base + ".txt")
            ref = html_p if os.path.exists(html_p) else txt_p
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(ref)))
            kinds = ("HTML" if os.path.exists(html_p) else "") + \
                    ("+TXT" if os.path.exists(txt_p) else "")
            # 文件名格式：网络测试报告_{类型}_{机器}_{时间}；旧文件类型取“未知”
            parts = os.path.basename(base).split("_")
            rtype = parts[1] if len(parts) > 1 else "未知"
            self.history_table.insert("", "end", values=(rtype, base, mtime, kinds, d))
        self.history_hint.config(text=f"共 {len(bases)} 条记录，双击任意一条可打开 HTML 报告")

    def _open_history(self, ext=".html"):
        sel = self.history_table.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择一条记录")
            return
        base = self.history_table.item(sel[0])["values"][1]  # 类型列之后是文件名
        path = os.path.join(self.config.report_dir, base + ext)
        if os.path.exists(path):
            webbrowser.open("file://" + os.path.abspath(path))
        else:
            messagebox.showinfo("提示", f"该记录没有 {ext} 文件")

    def _delete_history(self):
        sel = self.history_table.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择要删除的记录")
            return
        if not messagebox.askyesno("确认删除", "确定删除所选记录？（HTML 与 TXT 一并删除，不可恢复）"):
            return
        for item in sel:
            base = self.history_table.item(item)["values"][1]  # 类型列之后是文件名
            for ext in (".html", ".txt"):
                p = os.path.join(self.config.report_dir, base + ext)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        self._refresh_history()

    def _open_report_dir(self):
        d = self.config.report_dir
        if not os.path.isdir(d):
            try:
                os.makedirs(d, exist_ok=True)
            except OSError as exc:
                messagebox.showerror("无法打开", str(exc))
                return
        if os.name == "nt":
            os.startfile(d)  # noqa: S606 - 本地打开文件夹
        else:
            import subprocess
            subprocess.Popen(["xdg-open", d] if os.name == "posix" else ["open", d])

    # ---------- 测试执行 ----------
    def _start_default(self, subtype=""):
        self._run_custom("all", {
            "host": self.config.target_host,
            "port": self.config.target_port,
            "ping_count": self.config.ping_count,
            "duration": self.config.iperf_duration,
            "streams": self.config.parallel_streams,
            "reverse": True,
        }, report_type="quick", subtype=subtype)

    def _run_custom(self, mode, params=None, report_type="quick", subtype=None):
        if self._running:
            messagebox.showinfo("提示", "测试正在进行中，请稍候")
            return
        self._current_report_type = report_type
        # 子类型：高级探测细分（按参数/仅 Ping/仅端口/仅带宽/仅路由）
        if report_type == "advanced":
            self._current_report_subtype = {
                "all": "按参数", "ping": "仅 Ping", "tcp": "仅端口",
                "iperf": "仅带宽", "tracert": "仅路由",
            }.get(mode, "")
        elif subtype is not None:
            self._current_report_subtype = subtype
        else:
            self._current_report_subtype = ""
        cfg = self.config
        params = params or {}
        tests = self._build_tests(mode, params, cfg)

        self._running = True
        self._stop_flag.clear()
        # 新测试开始时清空旧残留记录，避免被启动自检误判
        platform_info.clear_pid_file()
        self._msg_queue.put(("begin", tests))
        t = threading.Thread(target=self._runner, args=(tests,), daemon=True)
        t.start()

    def _build_tests(self, mode: str, params: dict, cfg) -> list:
        """按模式与参数构造测试项列表（快速检测/高级探测共用）"""
        host = params.get("host", cfg.target_host)
        port = params.get("port", cfg.target_port)
        ping_n = params.get("ping_count", cfg.ping_count)
        dur = params.get("duration", cfg.iperf_duration)
        streams = params.get("streams", cfg.parallel_streams)
        src = cfg.source_ip

        tests = []
        if mode in ("all", "ping"):
            # verify_port：ping 全超时（禁 ping）时自动用 TCP 交叉验证
            tests.append(PingTest(host, count=ping_n, verify_port=port, src_ip=src))
        if mode in ("all", "tcp"):
            tests.append(TcpProbeTest(host, port, src_ip=src))
        if mode in ("all", "iperf"):
            # 带宽测试走独立的 iperf3 服务器（默认与外网映射一致）
            ih, ip = cfg.iperf3_host, cfg.iperf3_port
            tests.append(Iperf3Test(ih, ip, dur, streams, "single", cfg.reference_bandwidth,
                                    src_ip=src))
            # “仅带宽”单项与完整检测默认跑全三档（单流/并行/反向）；显式 reverse=False 除外
            if mode == "all" or params.get("reverse", True):
                tests.append(Iperf3Test(ih, ip, dur, streams, "parallel", cfg.reference_bandwidth,
                                        src_ip=src))
                tests.append(Iperf3Test(ih, ip, dur, streams, "reverse", cfg.reference_bandwidth,
                                        src_ip=src))
        if mode in ("all", "tracert"):
            tests.append(TracerouteTest(host, verify_port=port))
        # 出口连通性（公网目标，判断出口链路；政务网隔离公网时可关闭）
        if mode == "all" and cfg.egress_host:
            tests.append(EgressProbeTest(cfg.egress_host, cfg.egress_port, src_ip=src))
        if mode == "all" and cfg.app_host:
            # 一体化系统地址可能是 URL：DNS 解析提取主机名，HTTP 探测用完整 URL
            app_url = cfg.app_host
            dns_host = app_url
            if "://" in app_url:
                from urllib.parse import urlparse
                dns_host = urlparse(app_url).hostname or app_url
            tests.append(DnsResolveTest(dns_host))
            http_test = HttpProbeTest(app_url)
            # 依赖跳过：DNS 解析失败则 HTTP 探测无意义，自动跳过
            http_test.depends_on = "DNS 解析测试"
            tests.append(http_test)
        return tests

    def _request_stop(self):
        """一键停止测试：置中止信号，当前测试项 0.2s 内结束，不再执行后续项"""
        if not self._running:
            return
        self._stop_flag.set()
        self.set_status("● 正在停止…", theme.DANGER)
        self.stop_btn.config(state="disabled", text="⏹ 正在停止…")
        self.progress_lbl.config(text="正在停止测试，请稍候…（当前项结束后停止）")

    def _runner(self, tests):
        """后台线程：快项串行（保留依赖跳过），耗时项（iperf3/Tracert）并行，整体提速"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        start_time = time.strftime("%Y-%m-%d %H:%M:%S")
        aborted = False
        done_results = []

        def _run_one(idx, test):
            """执行单个测试并上报结果"""
            test.stop_event = self._stop_flag
            self._msg_queue.put(("progress", idx, len(tests), test.name))
            result = test.run()
            done_results.append(result.to_dict())
            self._msg_queue.put(("done", result.to_dict()))

        # 分类：慢项（iperf3/Tracert）并行；其余串行（含依赖跳过链）
        slow_names = ("iperf3", "Tracert")
        slow = [(i, t) for i, t in enumerate(tests) if any(s in t.name for s in slow_names)]
        fast = [(i, t) for i, t in enumerate(tests) if not any(s in t.name for s in slow_names)]

        # 1) 快项串行（依赖跳过在此处理）
        for i, test in fast:
            if self._stop_flag.is_set():
                aborted = True
                break
            dep = getattr(test, "depends_on", None)
            if dep and any(r["name"] == dep and r["status"] in ("bad", "error")
                           for r in done_results):
                self._msg_queue.put(("progress", i, len(tests), test.name))
                skipped = TestResult(name=test.name, status=STATUS_SKIP,
                                     detail=f"因前置项「{dep}」失败，本次自动跳过",
                                     message=f"前置项「{dep}」失败，无需继续该项检测")
                self._msg_queue.put(("done", skipped.to_dict()))
                done_results.append(skipped.to_dict())
                continue
            _run_one(i, test)

        # 2) 慢项并行（最多 3 个同时跑，大幅缩短总耗时）
        if slow and not aborted:
            with ThreadPoolExecutor(max_workers=min(3, len(slow))) as pool:
                futures = {pool.submit(_run_one, i, t): (i, t) for i, t in slow}
                for fut in as_completed(futures):
                    fut.result()  # 异常由 BaseTest.run 兜底
            if self._stop_flag.is_set():
                aborted = True

        self._msg_queue.put(("finish", start_time, aborted))

    def _poll_queue(self):
        """主线程轮询队列，更新界面"""
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                kind = msg[0]
                if kind == "begin":
                    self._render_progress_start(msg[1])
                    self.set_status("● 测试运行中", theme.WARNING)
                    self.hero_btn.config(text="⏳ 测试进行中，点击查看进度")
                    self.hero_hint_lbl.config(
                        text="切换页面不影响测试，点右上角状态指示或此处可随时回到进度")
                    self.show_page("progress")
                elif kind == "progress":
                    _, idx, total, name = msg
                    pct = int(idx / total * 100)
                    self.progress_bar["value"] = pct
                    self.progress_lbl.config(text=f"正在测试（{idx + 1}/{total}）：{name}")
                    self._set_progress_item(idx, "⏳ 进行中", theme.ACCENT)
                elif kind == "done":
                    r = msg[1]
                    self._collected_results.append(r)
                    self._set_progress_item(self._done_count, "✅ " + theme.STATUS_TEXT.get(r["status"], ""),
                                            theme.STATUS_COLOR.get(r["status"], theme.MUTED))
                    self._done_count += 1
                    if self._done_count == self._total_tests:
                        self.progress_bar["value"] = 100
                        self.progress_lbl.config(text="测试完成，正在生成报告…")
                elif kind == "server_status":
                    self._apply_server_status(msg[1], msg[2])
                elif kind == "finish":
                    self.set_status("● 空闲", theme.MUTED)
                    aborted = msg[2] if len(msg) > 2 else False
                    self.stop_btn.config(state="disabled", text="⏹ 停止测试")
                    self.hero_btn.config(text="▶  开始检测")
                    self.hero_hint_lbl.config(
                        text="点击后自动完成全部检测项 · 约需 3 分钟 · 全程无需操作")
                    self._finish_session(msg[1], aborted)
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    # ---------- 进度渲染 ----------
    def _render_progress_start(self, tests):
        self._total_tests = len(tests)
        self._done_count = 0
        self._collected_results = []
        self.progress_bar["value"] = 0
        self.stop_btn.config(state="normal", text="⏹ 停止测试")
        for w in self.progress_items.winfo_children():
            w.destroy()
        self._progress_rows = []
        for i, t in enumerate(tests):
            row = tk.Frame(self.progress_items, bg=theme.BG, highlightbackground=theme.LINE,
                           highlightthickness=1)
            row.pack(fill="x", pady=2)
            lbl = tk.Label(row, text=f"○ {t.name}", font=theme.ui_font(10), bg=theme.BG,
                           fg=theme.MUTED, anchor="w")
            lbl.pack(fill="x", padx=10, pady=5)
            self._progress_rows.append(lbl)

    def _set_progress_item(self, idx, status_text, color):
        if 0 <= idx < len(self._progress_rows):
            lbl = self._progress_rows[idx]
            name = lbl.cget("text").split(" ", 1)[-1]
            lbl.config(text=f"{status_text} {name}", fg=color, font=theme.ui_font(10, True))

    # ---------- 会话与报告 ----------
    def _finish_session(self, start_time, aborted=False):
        self._running = False
        results = getattr(self, "_collected_results", [])
        self.session = {
            "tool_version": "1.0",
            "start_time": start_time,
            "report_type": self._current_report_type,
            "report_subtype": self._current_report_subtype,
            "system_info": self.sys_info,
            "target": {"host": self.config.target_host, "port": self.config.target_port},
            "inner_target": f"{self.config.inner_host}:{self.config.inner_port}",
            "results": results,
            "aborted": aborted,
        }
        # 注：检测报告不合并监测结果——监测有独立报告（长期监测自动生成）
        concl = evaluate_session(self.session)
        if aborted:
            concl["title"] = "测试已中止（仅部分结果）"
            concl["suggestion"] = (
                f"测试被手动停止，共完成 {len(results)} 项。已完成项的结果可参考，"
                "建议稍后重新测试获取完整结论。")
        self.session["conclusion"] = concl
        self._attach_compare()
        self._render_report(self.session)
        self._auto_save_report()
        self.show_page("report")
        platform_info.clear_pid_file()

    def _attach_compare(self):
        """历史基线对比：与同类型最近一次报告对比指标，写入 session['compare_text']"""
        try:
            import re as _re
            from report.html_report import load_previous_metrics, build_compare_text
            sess = self.session
            prev = load_previous_metrics(self.config.report_dir,
                                         sess.get("report_type", "quick"),
                                         sess.get("report_subtype", ""))
            bw = sess.get("conclusion", {}).get("bandwidth") or {}
            cur = {"up": bw.get("up"), "down": bw.get("down")}
            for r in sess.get("results", []):
                km = r.get("key_metrics", {})
                if r.get("name", "").startswith("Ping"):
                    for key, field in (("平均延迟", "latency"), ("丢包", "loss")):
                        m = _re.search(r"[\d.]+", str(km.get(key, "")))
                        if m:
                            cur[field] = float(m.group(0))
            txt = build_compare_text(cur, prev)
            if txt:
                sess["compare_text"] = txt
        except Exception:  # noqa: BLE001 - 对比失败不影响报告
            pass

    def _generate_monitor_report(self):
        """长期监测结束后：生成监测报告（时间线 + 评级）并展示"""
        try:
            self._do_generate_monitor_report()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            panel = getattr(self.pages.get("monitor"), "panel", None)
            if panel is not None:
                panel._log(f"❌ 报告生成失败：{exc}\n", "bad")

    def _do_generate_monitor_report(self):
        """监测报告生成主逻辑（异常由 _generate_monitor_report 兜底）"""
        panel = getattr(self.pages.get("monitor"), "panel", None)
        if panel is None:
            return
        mon = panel.collect()
        if not mon:
            return
        summary = mon["summary"]
        level = summary.get("level", "C")
        status = "ok" if level == "A" else ("warn" if level == "B" else "bad")
        result = {
            "name": "长期监测",
            "status": status,
            "key_metrics": {
                "采样次数": f"{summary.get('samples', 0)} 次",
                "异常占比": f"{summary.get('bad_ratio', 0)}%",
                "捕获事件": f"{summary.get('events', 0)} 个",
                "稳定性评级": level,
            },
            "detail": f"监测 {summary.get('samples', 0)} 次采样，异常占比 "
                      f"{summary.get('bad_ratio', 0)}%，稳定性评级 {level}"
                      f"（{summary.get('verdict', '')}）",
            "message": summary.get("verdict", ""),
        }
        # 监测子类型：时长（如 3分钟 / 持续）
        dur_sec = getattr(panel, "dur_seconds", None)
        monitor_sub = f"{dur_sec // 60}分钟" if dur_sec else "持续"
        self.session = {
            "tool_version": "1.0",
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": "monitor",
            "report_subtype": monitor_sub,
            "system_info": self.sys_info,
            "target": {"host": self.config.target_host, "port": self.config.target_port},
            "inner_target": f"{self.config.inner_host}:{self.config.inner_port}",
            "results": [result],
            "aborted": False,
            "monitor_summary": mon["summary"],
            "monitor_events": mon["events"],
            "monitor_samples": [s.to_dict() for s in panel.monitor.samples],
        }
        self.session["conclusion"] = evaluate_session(self.session)
        self._render_report(self.session)
        self._auto_save_report()
        self.show_page("report")

    def _auto_save_report(self):
        """测试完成后自动保存 HTML + TXT 报告到配置目录（无需用户操作）"""
        self._last_report = None
        try:
            os.makedirs(self.config.report_dir, exist_ok=True)
            self._last_report = save_report(self.session, self.config.report_dir)
            self.report_hint.config(
                text=f"📁 报告已自动保存：{self._last_report['html']}\n"
                     f"   TXT 日志：{self._last_report['txt']}（可直接发送运维）",
                fg=theme.SUCCESS)
        except OSError as exc:
            self.report_hint.config(
                text=f"⚠️ 报告自动保存失败（{exc}），请点击下方「保存 HTML 报告」手动保存",
                fg=theme.WARNING)

    def _render_report(self, session):
        concl = session["conclusion"]
        score = concl["score"]
        # 横幅颜色跟随语义：存在异常项->红，警告->黄，中止/信息->灰，全正常->绿
        if session.get("aborted"):
            bg, fg, icon = "#F0F3F6", theme.MUTED, "⏹"
        else:
            statuses = [r.get("status") for r in session.get("results", [])]
            if any(s in ("bad", "error") for s in statuses):
                bg, fg, icon = theme.DANGER_LIGHT, "#B23A3A", "🔴"
            elif any(s == "warn" for s in statuses):
                bg, fg, icon = theme.WARNING_LIGHT, "#B06A12", "🟡"
            else:
                bg, fg, icon = theme.SUCCESS_LIGHT, theme.SUCCESS, "🟢"
        self.banner.config(bg=bg)
        self.banner_icon.config(bg=bg, text=icon)
        self.banner_title.config(bg=bg, fg=fg, text=f"{icon} {concl['title']}（{score} 分）")
        self.banner_desc.config(bg=bg, fg=fg, text=concl["suggestion"])

        for w in self.metrics_frame.winfo_children():
            w.destroy()
        metrics = []
        seen = set()
        for r in session["results"]:
            for k, v in r.get("key_metrics", {}).items():
                key = f"{r['name']}·{k}"
                if key not in seen:
                    seen.add(key)
                    metrics.append((key, v, theme.STATUS_COLOR.get(r["status"], theme.PRIMARY)))
        for i, (k, v, color) in enumerate(metrics[:6]):
            cell = tk.Frame(self.metrics_frame, bg=theme.BG, highlightbackground=theme.LINE,
                            highlightthickness=1)
            cell.grid(row=0, column=i % 3, rowspan=1 + (i // 3), padx=5, pady=5, sticky="nsew")
            tk.Label(cell, text=k, font=theme.ui_font(8), bg=theme.BG, fg=theme.MUTED
                     ).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(cell, text=str(v), font=theme.ui_font(14, True), bg=theme.BG, fg=color
                     ).pack(anchor="w", padx=8, pady=(0, 6))
        for col in range(3):
            self.metrics_frame.grid_columnconfigure(col, weight=1)

        for item in self.report_table.get_children():
            self.report_table.delete(item)
        for r in session["results"]:
            detail = (r.get("detail") or r.get("message") or "")[:60]
            hint = r.get("hint", "")
            if hint:
                detail += f" ｜💡{hint[:26]}"
            self.report_table.insert("", "end", values=(
                r["name"],
                detail,
                theme.STATUS_TEXT.get(r["status"], r["status"])))

    def _copy_summary(self):
        if not self.session:
            return
        text = build_wechat_summary(self.session)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已复制", "摘要已复制到剪贴板，可直接粘贴到微信发给运维")

    def _save_html(self):
        if not self.session:
            return
        default_dir = self.config.report_dir
        path = filedialog.asksaveasfilename(
            title="保存网络测试报告", initialdir=default_dir, defaultextension=".html",
            initialfile=f"网络测试报告_{self.sys_info.get('hostname', 'machine')}",
            filetypes=[("HTML 报告", "*.html"), ("全部文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_html_report(self.session))
            messagebox.showinfo("保存成功", f"报告已保存：\n{path}")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc))

    def _open_browser(self):
        if not self.session:
            return
        path = None
        if getattr(self, "_last_report", None):
            path = self._last_report["html"]
        if not path or not os.path.exists(path):
            os.makedirs(self.config.report_dir, exist_ok=True)
            self._last_report = save_report(self.session, self.config.report_dir)
            path = self._last_report["html"]
        webbrowser.open("file://" + os.path.abspath(path))

    # ---------- 系统自检 ----------
    def _check_server_status(self):
        """真实探测多目标连通性（TCP 为主，不依赖 ICMP）：
        - 外网映射端口（一体化系统/网关）
        - iperf3 服务器端口（如与映射不同）
        - 一体化系统 HTTP 地址（若已配置）
        """
        cfg = self.config
        self.server_state.config(text="⋯ 检测中…", fg=theme.MUTED)

        def probe():
            lines = []
            # 1. 外网映射端口
            r1 = TcpProbeTest(cfg.target_host, cfg.target_port, timeout=8).run()
            mark1 = "●" if r1.status == "ok" else "○"
            lines.append(f"{mark1} 映射 {cfg.target_host}:{cfg.target_port} "
                         + ("在线" if r1.status == "ok" else "离线"))
            # 2. iperf3 服务器（与映射不同才单独探测）
            if (cfg.iperf3_host, cfg.iperf3_port) != (cfg.target_host, cfg.target_port):
                r2 = TcpProbeTest(cfg.iperf3_host, cfg.iperf3_port, timeout=8).run()
                mark2 = "●" if r2.status == "ok" else "○"
                lines.append(f"{mark2} iperf3 {cfg.iperf3_host}:{cfg.iperf3_port} "
                             + ("在线" if r2.status == "ok" else "离线"))
            # 3. 一体化系统 HTTP（若已配置）
            if cfg.app_host:
                hr = HttpProbeTest(cfg.app_host, timeout=8, samples=1).run()
                mark3 = "●" if hr.status in ("ok", "warn") else "○"
                lines.append(f"{mark3} 一体化系统 "
                             + (f"HTTP {hr.key_metrics.get('HTTP 状态', '?')}"
                                if hr.status in ("ok", "warn", "bad") and hr.key_metrics
                                else "不可达"))
            self._msg_queue.put(("server_status", "\n".join(lines), r1.status))

        threading.Thread(target=probe, daemon=True).start()

    def _apply_server_status(self, text, status):
        """多目标状态显示：按映射目标在线与否决定主色"""
        if status == "ok":
            self.server_state.config(text=text, fg=theme.SUCCESS)
        else:
            self.server_state.config(text=text, fg=theme.DANGER)

    def _check_platform(self):
        expect = platform_info.match_package_type()
        actual = self.sys_info.get("package_type", "")
        if expect and actual != expect:
            messagebox.showwarning(
                "系统版本提示",
                f"当前系统：{self.sys_info.get('os_version', '')}（{self.sys_info.get('arch_detail', '')}）\n\n"
                f"当前程序包适用于：{self._pkg_name(actual)}\n"
                f"如遇功能异常，请使用：{self._pkg_name(expect)}\n\n"
                "（此提示不影响使用，仅用于提醒）")

    def _sched_tick(self):
        """定时自动检测：到设定时间自动跑快速检测并保存报告（静默）"""
        try:
            if self.config.sched_enabled and not self._running:
                today = time.strftime("%Y-%m-%d")
                if time.strftime("%H:%M") == self.config.sched_time and self._sched_last != today:
                    self._sched_last = today
                    self._start_default(subtype="定时自动")
        except Exception:  # noqa: BLE001
            pass
        self.after(30000, self._sched_tick)

    def _check_stale(self):
        """启动自检：检测上次异常退出遗留的 iperf3 进程，询问是否强制结束
        若用户已开始新测试（_running），跳过检查避免误弹。"""
        if self._running:
            return
        alive = platform_info.check_stale_processes()
        if not alive:
            return
        if messagebox.askyesno(
                "检测到未结束的测试进程",
                "上次测试可能被强制关闭，仍有测试进程未结束：\n\n"
                f"PID: {', '.join(map(str, alive))}\n\n"
                "是否强制结束这些进程？"):
            for pid in alive:
                platform_info.kill_process(pid)
        platform_info.clear_pid_file()

    @staticmethod
    def _pkg_name(pkg: str) -> str:
        return {"win32": "Windows 32 位", "win64": "Windows 64 位",
                "kylin_x64": "麒麟 x86_64", "kylin_arm64": "麒麟 ARM64",
                "macos_x64": "macOS Intel", "macos_arm64": "macOS Apple 芯片"
                }.get(pkg, pkg or "未知")
