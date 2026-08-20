# -*- coding: utf-8 -*-
"""
可复用控件：ScrollableFrame 垂直滚动容器。
用于所有页面，解决窗口缩放/内容较多时显示不完整的问题。
"""
import tkinter as tk
from tkinter import ttk

from . import theme


class ScrollableFrame(tk.Frame):
    """
    垂直可滚动 Frame：
    - 把内容控件 pack 到 .inner 上即可
    - 自动出现/隐藏滚动条；支持鼠标滚轮（悬停时生效）
    """

    def __init__(self, master, bg=theme.BG, **kw):
        super().__init__(master, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # 内容容器
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._win_id, width=e.width))

        # 鼠标滚轮：悬停本区域时生效，离开后解除（避免多页面冲突）
        self._wheel_binding = None

        def _on_enter(_event):
            self._wheel_binding = self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        def _on_leave(_event):
            if self._wheel_binding is not None:
                self.canvas.unbind_all("<MouseWheel>")
                self._wheel_binding = None

        self.canvas.bind("<Enter>", _on_enter)
        self.canvas.bind("<Leave>", _on_leave)

    def _on_mousewheel(self, event):
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)
