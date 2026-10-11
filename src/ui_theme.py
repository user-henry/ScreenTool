"""
ScreenTool 统一 UI 主题（暗色科技风 v2）

- 集中管理配色、字体、ttk 样式
- 提供卡片、徽章、分类标签、提示条、滚动容器等基础组件
- 所有组件均为纯 tkinter / ttk 实现，无额外依赖
"""

import tkinter as tk
from tkinter import ttk


# ── 调色板 ──
COLORS = {
    "bg": "#0B1020",
    "bg_alt": "#0E1526",
    "panel": "#121A2E",
    "card": "#16203A",
    "card_hover": "#1D2A4A",
    "card_active": "#22325A",
    "border": "#22304F",
    "border_light": "#2E4165",
    "text": "#E8F1FF",
    "text_dim": "#8CA0C4",
    "text_mute": "#5F719A",
    "accent": "#3DE1FF",
    "accent_dim": "#1B7E93",
    "accent2": "#7C5CFF",
    "success": "#35D07F",
    "warn": "#FFB020",
    "danger": "#FF5C6C",
    "input": "#0F1729",
}

FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

# 分类配色（按名称稳定分配）
CATEGORY_COLORS = [
    "#3DE1FF", "#7C5CFF", "#35D07F", "#FFB020",
    "#FF5C6C", "#FF7AD9", "#4ADE80", "#38BDF8",
]


def font(size=10, bold=False):
    """返回 UI 字体元组"""
    return (FONT_FAMILY, size, "bold" if bold else "normal")


def mono(size=10, bold=False):
    """返回等宽字体元组"""
    return (FONT_MONO, size, "bold" if bold else "normal")


def category_color(name: str) -> str:
    """按名称稳定地分配一个分类颜色"""
    if not name:
        return COLORS["text_mute"]
    acc = 0
    for ch in name:
        acc = (acc * 131 + ord(ch)) & 0xFFFFFFFF
    return CATEGORY_COLORS[acc % len(CATEGORY_COLORS)]


# ════════════════════════════════════════════
# ttk 样式
# ════════════════════════════════════════════

def _safe_configure(style: ttk.Style, name: str, mapping: dict, style_map: dict = None):
    """逐个选项容错地配置 ttk 样式（不同 ttk 版本支持度不同）"""
    try:
        style.configure(name, **mapping)
    except Exception:
        for key, value in mapping.items():
            try:
                style.configure(name, **{key: value})
            except Exception:
                pass
    if style_map:
        try:
            style.map(name, **style_map)
        except Exception:
            for key, value in style_map.items():
                try:
                    style.map(name, **{key: value})
                except Exception:
                    pass


def apply(root: tk.Misc, accent: str = None) -> ttk.Style:
    """
    应用主题到 ttk 与 tk 控件。

    Args:
        root: 任意 Tk/Toplevel
        accent: 可选强调色覆盖

    Returns:
        配置完成后的 ttk.Style 对象
    """
    if accent:
        COLORS["accent"] = accent

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    c = COLORS
    cfg = lambda n, m, s=None: _safe_configure(style, n, m, s)  # noqa: E731

    # ── 基础容器 ──
    cfg("TFrame", {"background": c["bg"]})
    cfg("Panel.TFrame", {"background": c["panel"]})
    cfg("Card.TFrame", {"background": c["card"], "relief": "flat"})
    cfg("Bg.TFrame", {"background": c["bg_alt"]})
    cfg("Header.TFrame", {"background": c["panel"]})

    # ── 文本 ──
    cfg("TLabel", {"background": c["bg"], "foreground": c["text"], "font": font(10)})
    cfg("Panel.TLabel", {"background": c["panel"], "foreground": c["text"], "font": font(10)})
    cfg("Card.TLabel", {"background": c["card"], "foreground": c["text"], "font": font(10)})
    cfg("Alt.TLabel", {"background": c["bg_alt"], "foreground": c["text"], "font": font(10)})
    cfg("Title.TLabel", {"background": c["bg"], "foreground": c["text"], "font": font(15, True)})
    cfg("PanelTitle.TLabel", {"background": c["panel"], "foreground": c["text"], "font": font(14, True)})
    cfg("CardTitle.TLabel", {"background": c["card"], "foreground": c["text"], "font": font(11, True)})
    cfg("Dim.TLabel", {"background": c["bg"], "foreground": c["text_dim"], "font": font(9)})
    cfg("PanelDim.TLabel", {"background": c["panel"], "foreground": c["text_dim"], "font": font(9)})
    cfg("CardDim.TLabel", {"background": c["card"], "foreground": c["text_dim"], "font": font(9)})
    cfg("Mute.TLabel", {"background": c["bg"], "foreground": c["text_mute"], "font": font(9)})
    cfg("CardMute.TLabel", {"background": c["card"], "foreground": c["text_mute"], "font": font(8)})
    cfg("Accent.TLabel", {"background": c["bg"], "foreground": c["accent"], "font": font(10, True)})
    cfg("PanelAccent.TLabel", {"background": c["panel"], "foreground": c["accent"], "font": font(10, True)})
    cfg("Section.TLabel", {"background": c["panel"], "foreground": c["accent"], "font": font(10, True)})

    # ── 按钮 ──
    cfg("TButton", {
        "background": c["card"], "foreground": c["text"],
        "bordercolor": c["border"], "lightcolor": c["card"], "darkcolor": c["card"],
        "focuscolor": c["card"], "font": font(9), "padding": (12, 6), "relief": "flat",
    }, {
        "background": [("pressed", c["card_active"]), ("active", c["card_hover"])],
        "foreground": [("disabled", c["text_mute"])],
    })

    cfg("Accent.TButton", {
        "background": c["accent"], "foreground": "#062033",
        "bordercolor": c["accent"], "lightcolor": c["accent"], "darkcolor": c["accent"],
        "focuscolor": c["accent"], "font": font(9, True), "padding": (12, 6), "relief": "flat",
    }, {
        "background": [("pressed", c["accent_dim"]), ("active", "#6CEBFF")],
        "foreground": [("disabled", "#5C7488")],
    })

    cfg("Ghost.TButton", {
        "background": c["panel"], "foreground": c["text_dim"],
        "bordercolor": c["panel"], "lightcolor": c["panel"], "darkcolor": c["panel"],
        "focuscolor": c["panel"], "font": font(9), "padding": (10, 5), "relief": "flat",
    }, {
        "background": [("active", c["card_hover"])],
        "foreground": [("active", c["text"])],
    })

    cfg("CardGhost.TButton", {
        "background": c["card"], "foreground": c["text_dim"],
        "bordercolor": c["card"], "lightcolor": c["card"], "darkcolor": c["card"],
        "focuscolor": c["card"], "font": font(8), "padding": (8, 3), "relief": "flat",
    }, {
        "background": [("active", c["card_hover"])],
        "foreground": [("active", c["accent"])],
    })

    cfg("Danger.TButton", {
        "background": c["card"], "foreground": c["danger"],
        "bordercolor": c["border"], "lightcolor": c["card"], "darkcolor": c["card"],
        "focuscolor": c["card"], "font": font(9), "padding": (12, 6), "relief": "flat",
    }, {
        "background": [("active", "#2A1526"), ("pressed", "#3A1A2E")],
    })

    cfg("Tool.TButton", {
        "background": c["card"], "foreground": c["text_dim"],
        "bordercolor": c["card"], "lightcolor": c["card"], "darkcolor": c["card"],
        "focuscolor": c["card"], "font": font(9), "padding": (10, 5), "relief": "flat",
    }, {
        "background": [("active", c["card_hover"])],
        "foreground": [("active", c["text"])],
    })

    cfg("ToolActive.TButton", {
        "background": c["accent"], "foreground": "#062033",
        "bordercolor": c["accent"], "lightcolor": c["accent"], "darkcolor": c["accent"],
        "focuscolor": c["accent"], "font": font(9, True), "padding": (10, 5), "relief": "flat",
    }, {
        "background": [("active", "#6CEBFF")],
    })

    # ── 输入控件 ──
    cfg("TEntry", {
        "fieldbackground": c["input"], "foreground": c["text"],
        "bordercolor": c["border"], "insertcolor": c["accent"],
        "lightcolor": c["border"], "darkcolor": c["border"], "padding": 6,
    }, {"bordercolor": [("focus", c["accent"])]})

    cfg("Card.TEntry", {
        "fieldbackground": c["input"], "foreground": c["text"],
        "bordercolor": c["border"], "insertcolor": c["accent"], "padding": 4,
    }, {"bordercolor": [("focus", c["accent"])]})

    cfg("TCombobox", {
        "fieldbackground": c["input"], "background": c["input"], "foreground": c["text"],
        "bordercolor": c["border"], "arrowcolor": c["accent"],
        "lightcolor": c["border"], "darkcolor": c["border"], "padding": 4,
    }, {
        "fieldbackground": [("readonly", c["input"])],
        "foreground": [("readonly", c["text"])],
        "bordercolor": [("focus", c["accent"])],
    })

    cfg("TSpinbox", {
        "fieldbackground": c["input"], "foreground": c["text"],
        "background": c["card"], "bordercolor": c["border"],
        "arrowcolor": c["accent"], "padding": 4,
    })

    cfg("TCheckbutton", {
        "background": c["bg"], "foreground": c["text"], "font": font(9),
        "focuscolor": c["bg"],
    }, {
        "background": [("active", c["bg"])],
        "indicatorcolor": [("selected", c["accent"]), ("!selected", c["input"])],
    })

    cfg("Card.TCheckbutton", {
        "background": c["card"], "foreground": c["text"], "font": font(9),
        "focuscolor": c["card"],
    }, {
        "background": [("active", c["card"])],
        "indicatorcolor": [("selected", c["accent"]), ("!selected", c["input"])],
    })

    cfg("Panel.TCheckbutton", {
        "background": c["panel"], "foreground": c["text"], "font": font(9),
        "focuscolor": c["panel"],
    }, {
        "background": [("active", c["panel"])],
        "indicatorcolor": [("selected", c["accent"]), ("!selected", c["input"])],
    })

    cfg("TRadiobutton", {"background": c["bg"], "foreground": c["text"], "font": font(9)},
        {"background": [("active", c["bg"])]})
    cfg("Panel.TRadiobutton", {"background": c["panel"], "foreground": c["text"], "font": font(9)},
        {"background": [("active", c["panel"])]})

    # ── 滚动条 ──
    for orient in ("Vertical", "Horizontal"):
        cfg(f"{orient}.TScrollbar", {
            "background": c["card"], "troughcolor": c["bg_alt"],
            "bordercolor": c["bg_alt"], "arrowcolor": c["text_dim"],
            "lightcolor": c["card"], "darkcolor": c["card"], "relief": "flat",
        }, {"background": [("active", c["accent_dim"])]})

    # ── 分隔线 ──
    cfg("TSeparator", {"background": c["border"]})

    # ── Notebook（设置页） ──
    cfg("TNotebook", {"background": c["bg"], "bordercolor": c["border"], "tabmargins": (6, 6, 6, 0)})
    cfg("TNotebook.Tab", {
        "background": c["panel"], "foreground": c["text_dim"],
        "padding": (16, 8), "font": font(9), "bordercolor": c["border"],
    }, {
        "background": [("selected", c["card"])],
        "foreground": [("selected", c["accent"])],
    })

    # ── 刻度条 / 进度条 ──
    cfg("Horizontal.TScale", {
        "background": c["panel"], "troughcolor": c["input"],
        "bordercolor": c["border"], "lightcolor": c["accent"], "darkcolor": c["accent"],
    })
    cfg("Horizontal.TProgressbar", {
        "background": c["accent"], "troughcolor": c["input"], "bordercolor": c["input"],
        "lightcolor": c["accent"], "darkcolor": c["accent"],
    })

    # ── Treeview（备用） ──
    cfg("Treeview", {
        "background": c["card"], "fieldbackground": c["card"],
        "foreground": c["text"], "bordercolor": c["border"], "font": font(9),
    }, {"background": [("selected", c["card_active"])]})
    cfg("Treeview.Heading", {
        "background": c["panel"], "foreground": c["text_dim"], "font": font(9, True),
    })

    return style


# ════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════

def hover(widget, normal: str, active: str, cursor: str = "hand2"):
    """给 tk 控件绑定鼠标悬停配色"""
    def on_enter(_e):
        try:
            widget.configure(bg=active, cursor=cursor)
        except Exception:
            pass

    def on_leave(_e):
        try:
            widget.configure(bg=normal)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
    return widget


def center_window(win: tk.Misc, width: int = None, height: int = None,
                  parent: tk.Misc = None, offset_y: int = 0):
    """把窗口居中（相对 parent 或屏幕）"""
    try:
        win.update_idletasks()
        w = width or win.winfo_width()
        h = height or win.winfo_height()
        if parent is not None and parent.winfo_exists() and parent.winfo_width() > 1:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
        else:
            x = (win.winfo_screenwidth() - w) // 2
            y = (win.winfo_screenheight() - h) // 2
        x = max(0, x)
        y = max(0, y + offset_y)
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r=8, **kwargs):
    """在 Canvas 上绘制圆角矩形，返回 item id 列表"""
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def separator(parent, bg=None, pady=0):
    """一条 1px 分隔线"""
    bg = bg or COLORS["border"]
    holder = tk.Frame(parent, bg=parent["bg"] if isinstance(parent, tk.Frame) else COLORS["bg"])
    holder.pack(fill=tk.X, pady=pady)
    line = tk.Frame(holder, bg=bg, height=1)
    line.pack(fill=tk.X)
    return line


# ════════════════════════════════════════════
# 基础组件
# ════════════════════════════════════════════

class Chip(tk.Frame):
    """
    分类标签：彩色圆点 + 名称。
    clickable=True 时支持点击回调。
    """

    def __init__(self, parent, text: str, color: str = None, bg: str = None,
                 fg: str = None, on_click=None, active: bool = False, **kwargs):
        self.color = color or category_color(text)
        bg = bg if active else (bg or COLORS["card"])
        if active:
            bg = COLORS["card_active"]
        super().__init__(parent, bg=bg, padx=6, pady=2, **kwargs)

        self._bg = bg
        self._active = active
        self._dot = tk.Frame(self, bg=self.color, width=7, height=7,
                             highlightthickness=0, bd=0)
        self._dot.pack(side=tk.LEFT, padx=(0, 5))
        self._dot.pack_propagate(False)

        self._label = tk.Label(
            self, text=text, bg=bg,
            fg=(fg or (COLORS["text"] if active else COLORS["text_dim"])),
            font=font(8, active),
        )
        self._label.pack(side=tk.LEFT)

        if on_click:
            self._on_click = on_click
            for w in (self, self._dot, self._label):
                w.bind("<Button-1>", lambda e: self._on_click())
                w.configure(cursor="hand2")

    def set_active(self, active: bool):
        self._active = active
        bg = COLORS["card_active"] if active else self._bg
        for w in (self, self._label):
            try:
                w.configure(bg=bg)
            except Exception:
                pass
        try:
            self._label.configure(
                font=font(8, active),
                fg=COLORS["text"] if active else COLORS["text_dim"],
            )
        except Exception:
            pass


class Badge(tk.Label):
    """小徽章（用于“已复制 / 密码 / 数量”等提示）"""

    def __init__(self, parent, text: str, color: str = None, bg: str = None, **kwargs):
        color = color or COLORS["accent"]
        bg = bg or COLORS["card"]
        super().__init__(
            parent, text=text, bg=bg, fg=color,
            font=font(8, True), padx=6, pady=1, **kwargs,
        )


class CardContainer(tk.Frame):
    """
    卡片容器：1px 边框 + 悬停高亮 + 选中高亮。

    用法：
        card = CardContainer(parent)
        card.body  # 把内容放进这里
    """

    def __init__(self, parent, bg=None, border=None, radius=8,
                 padding=10, hover_bg=None, selectable=True, **kwargs):
        self._bg = bg or COLORS["card"]
        self._hover_bg = hover_bg or COLORS["card_hover"]
        self._border = border or COLORS["border"]
        self._selectable = selectable
        self._selected = False

        super().__init__(parent, bg=self._border, highlightthickness=0, bd=0, **kwargs)

        self.body = tk.Frame(self, bg=self._bg, padx=padding, pady=padding)
        self.body.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._bind_hover(self)

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _all_bg_widgets(self):
        out = [self.body]
        return out

    def _on_enter(self, _e=None):
        if self._selected:
            return
        self._paint(self._hover_bg)

    def _on_leave(self, _e=None):
        if self._selected:
            return
        self._paint(self._bg)

    def _paint(self, color: str):
        try:
            for w in self._all_bg_widgets():
                w.configure(bg=color)
        except Exception:
            pass

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            try:
                self.configure(bg=COLORS["accent"])
            except Exception:
                pass
            self._paint(COLORS["card_active"])
        else:
            try:
                self.configure(bg=self._border)
            except Exception:
                pass
            self._paint(self._bg)

    def bind_click(self, callback, double=False):
        """把整张卡片的点击绑定到回调"""
        def handler(_e=None):
            callback()
        for w in [self, self.body]:
            w.bind("<Button-1>", handler)
        if double:
            for w in [self, self.body]:
                w.bind("<Double-Button-1>", handler)
        return self


class ScrollableFrame(tk.Frame):
    """带垂直滚动条的容器，内容放到 self.inner"""

    _active = None

    def __init__(self, parent, bg=None, **kwargs):
        bg = bg or COLORS["bg"]
        super().__init__(parent, bg=bg, **kwargs)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    # ── 内部事件 ──

    def _on_inner_configure(self, _event=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event):
        try:
            self.canvas.itemconfigure(self._win, width=event.width)
        except Exception:
            pass

    def _on_scroll(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.vbar.pack_forget()
        else:
            self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        try:
            self.vbar.set(first, last)
        except Exception:
            pass

    def _bind_wheel(self, _event=None):
        ScrollableFrame._active = self
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        if ScrollableFrame._active is self:
            ScrollableFrame._active = None
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

    def _on_wheel(self, event):
        if ScrollableFrame._active is not self:
            return
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass

    def clear(self):
        """清空内容"""
        for child in self.inner.winfo_children():
            child.destroy()

    def scroll_to_top(self):
        try:
            self.canvas.yview_moveto(0)
        except Exception:
            pass


# ════════════════════════════════════════════
# 悬浮提示（Toast）
# ════════════════════════════════════════════

_KIND_COLOR = {
    "info": COLORS["accent"],
    "success": COLORS["success"],
    "warn": COLORS["warn"],
    "error": COLORS["danger"],
}

_active_toasts = []


def glassify(win, settings=None, *, alpha=None, no_activate: bool = False) -> bool:
    """
    给窗口套上原生毛玻璃（按设置）。

    Args:
        win: 任意 tkinter 窗口
        settings: AppSettings 实例；None 表示用默认参数
        alpha: 覆盖窗口整体不透明度；None 表示读取设置或保持原样
        no_activate: 点击不抢焦点（用于提示条、绳子这类悬浮窗口）
    """
    try:
        import windows_fx
    except Exception:
        return False
    if not windows_fx.IS_WINDOWS:
        return False

    enabled = True
    mode = "blur"
    tint = COLORS["bg"]
    tint_alpha = 112
    use_alpha = alpha
    if settings is not None:
        try:
            enabled = bool(settings.get("glass_enabled", True))
            mode = settings.get("glass_mode", "blur") or "blur"
            tint = settings.get("glass_tint", COLORS["bg"]) or COLORS["bg"]
            tint_alpha = int(settings.get("glass_tint_alpha", 112) or 112)
            if use_alpha is None:
                use_alpha = float(settings.get("glass_alpha", 0.97) or 0.97)
        except Exception:
            pass
    if not enabled:
        return False
    try:
        return windows_fx.apply_glass(
            win, tint=tint, tint_alpha=tint_alpha, mode=mode,
            alpha=use_alpha, rounded=True, no_activate=no_activate)
    except Exception:
        return False


def toast(root: tk.Misc, title: str, message: str = "", kind: str = "info",
          duration: int = 2400):
    """
    屏幕右下角显示一条悬浮提示（自动消失）。

    必须在 tkinter 主线程调用。
    """
    try:
        win = tk.Toplevel(root)
    except Exception:
        return None

    accent = _KIND_COLOR.get(kind, COLORS["accent"])
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.configure(bg=COLORS["border"])
    try:
        glassify(win, None, alpha=None, no_activate=True)
    except Exception:
        pass
    try:
        win.attributes("-alpha", 0.0)
    except Exception:
        pass

    outer = tk.Frame(win, bg=COLORS["border"])
    outer.pack(fill=tk.BOTH, expand=True)

    bar = tk.Frame(outer, bg=accent, width=3)
    bar.pack(side=tk.LEFT, fill=tk.Y)

    inner = tk.Frame(outer, bg=COLORS["card"], padx=14, pady=10)
    inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tk.Label(inner, text=title, bg=COLORS["card"], fg=COLORS["text"],
             font=font(10, True), anchor="w", justify="left").pack(anchor="w")
    if message:
        tk.Label(inner, text=message, bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=font(8), anchor="w", justify="left", wraplength=260).pack(anchor="w", pady=(3, 0))

    closed = {"v": False}

    def close(_e=None):
        if closed["v"]:
            return
        closed["v"] = True
        try:
            _active_toasts.remove(win)
        except ValueError:
            pass
        try:
            win.destroy()
        except Exception:
            pass
        _restack_toasts()

    for w in (win, outer, inner, bar):
        w.bind("<Button-1>", close)

    _active_toasts.append(win)
    _restack_toasts()
    _fade(win, 0.0, 0.96, 8, 22)

    try:
        win.after(duration, lambda: _fade_out(win, close))
    except Exception:
        pass
    return win


def _restack_toasts():
    """把所有提示窗口从下往上堆叠在屏幕右下角"""
    try:
        if not _active_toasts:
            return
        ref = _active_toasts[-1]
        sw = ref.winfo_screenwidth()
        sh = ref.winfo_screenheight()
        y = sh - 70
        for win in reversed(_active_toasts):
            if not win.winfo_exists():
                continue
            win.update_idletasks()
            w = max(win.winfo_reqwidth(), 200)
            h = win.winfo_reqheight()
            x = sw - w - 24
            y -= (h + 8)
            win.geometry(f"{w}x{h}+{x}+{max(10, y)}")
    except Exception:
        pass


def _fade(win, current, target, steps, delay):
    if steps <= 0:
        try:
            win.attributes("-alpha", target)
        except Exception:
            pass
        return
    nxt = current + (target - current) / steps
    try:
        win.attributes("-alpha", nxt)
        win.after(delay, lambda: _fade(win, nxt, target, steps - 1, delay))
    except Exception:
        pass


def _fade_out(win, on_done):
    def step(alpha, remaining):
        if remaining <= 0:
            on_done()
            return
        try:
            win.attributes("-alpha", alpha)
            win.after(18, lambda: step(alpha - 0.12, remaining - 1))
        except Exception:
            on_done()

    try:
        step(0.96, 8)
    except Exception:
        on_done()


def close_all_toasts():
    """关闭所有提示窗口"""
    for win in list(_active_toasts):
        try:
            win.destroy()
        except Exception:
            pass
    _active_toasts.clear()


# ════════════════════════════════════════════
# 暗色模态对话框
# ════════════════════════════════════════════

def _modal_shell(parent, title: str, width: int = 420, accent: str = None):
    """创建一个暗色模态窗口，返回 (win, body)"""
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=COLORS["bg"])
    try:
        glassify(win, None, alpha=0.97)
    except Exception:
        pass
    win.resizable(False, False)
    win.transient(parent)

    head = tk.Frame(win, bg=COLORS["panel"], padx=14, pady=10)
    head.pack(fill=tk.X)
    tk.Label(head, text=title, bg=COLORS["panel"], fg=COLORS["text"],
             font=font(11, True)).pack(side=tk.LEFT)
    tk.Frame(head, bg=accent or COLORS["accent"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

    body = tk.Frame(win, bg=COLORS["bg"], padx=16, pady=14)
    body.pack(fill=tk.BOTH, expand=True)
    return win, body


def _finish_modal(win):
    """统一收尾：取消 grab 并销毁窗口"""
    try:
        win.grab_release()
    except Exception:
        pass
    try:
        win.destroy()
    except Exception:
        pass


def prompt_fields(parent, title: str, fields: list, ok_text: str = "保存",
                  accent: str = None, width: int = 440) -> dict:
    """
    暗色风格的通用输入对话框。

    Args:
        fields: [{"key","label","type":"text"|"combo"|"multiline","value","options"}]

    Returns:
        字段字典；用户取消时返回 None
    """
    result = {"value": None, "widgets": {}}
    win, body = _modal_shell(parent, title, width, accent)

    entries = {}
    for field in fields:
        key = field["key"]
        label = field.get("label") or key
        ftype = field.get("type", "text")
        row = tk.Frame(body, bg=COLORS["bg"])
        row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(row, text=label, bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=font(9)).pack(anchor="w", pady=(0, 4))

        if ftype == "combo":
            var = tk.StringVar(value=str(field.get("value") or ""))
            box = ttk.Combobox(row, textvariable=var, values=field.get("options") or [],
                               state=field.get("state", "normal"))
            box.pack(fill=tk.X)
            box.configure(width=30)
            entries[key] = var
        elif ftype == "multiline":
            widget = tk.Text(row, height=field.get("height", 5), bg=COLORS["input"],
                             fg=COLORS["text"], insertbackground=COLORS["accent"],
                             relief=tk.FLAT, font=font(9), padx=6, pady=4,
                             highlightthickness=1, highlightbackground=COLORS["border"],
                             highlightcolor=COLORS["accent"], wrap=tk.WORD)
            widget.insert("1.0", str(field.get("value") or ""))
            widget.pack(fill=tk.X)
            entries[key] = widget
        else:
            var = tk.StringVar(value=str(field.get("value") or ""))
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(fill=tk.X)
            entries[key] = var

    hint = tk.Label(body, text="", bg=COLORS["bg"], fg=COLORS["danger"], font=font(8))
    hint.pack(anchor="w")

    def collect():
        out = {}
        for key, widget in entries.items():
            if isinstance(widget, tk.Text):
                out[key] = widget.get("1.0", tk.END).rstrip("\n")
            else:
                out[key] = widget.get()
        return out

    def cancel(_e=None):
        result["value"] = None
        _finish_modal(win)

    def ok(_e=None):
        values = collect()
        for field in fields:
            if field.get("required") and not str(values.get(field["key"], "")).strip():
                hint.configure(text=f"「{field.get('label') or field['key']}」不能为空")
                return
        result["value"] = values
        _finish_modal(win)

    btns = tk.Frame(body, bg=COLORS["bg"])
    btns.pack(fill=tk.X, pady=(6, 0))
    ttk.Button(btns, text="取消", style="Ghost.TButton", command=cancel).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btns, text=ok_text, style="Accent.TButton", command=ok).pack(side=tk.RIGHT, padx=4)

    win.bind("<Escape>", cancel)
    win.bind("<Return>", lambda e: ok())
    win.protocol("WM_DELETE_WINDOW", cancel)
    center_window(win, width, None, parent)
    try:
        win.grab_set()
        win.focus_force()
        first = list(entries.values())[0] if entries else None
        if isinstance(first, tk.Text):
            first.focus_set()
    except Exception:
        pass
    try:
        parent.wait_window(win)
    except Exception:
        pass
    return result["value"]


def prompt_text(parent, title: str, label: str = "", initial: str = "",
                multiline: bool = False, ok_text: str = "确定",
                accent: str = None) -> str:
    """暗色风格的文本输入框，返回字符串或 None"""
    fields = [{
        "key": "text", "label": label or "内容",
        "type": "multiline" if multiline else "text",
        "value": initial, "height": 6,
    }]
    values = prompt_fields(parent, title, fields, ok_text=ok_text, accent=accent)
    if not values:
        return None
    return values.get("text")


def prompt_choice(parent, title: str, label: str, options: list,
                  current: str = None, ok_text: str = "确定",
                  accent: str = None) -> str:
    """从若干选项中选择一个，返回选中的值或 None"""
    fields = [{
        "key": "choice", "label": label, "type": "combo",
        "value": current if current is not None else (options[0] if options else ""),
        "options": options, "state": "readonly",
    }]
    values = prompt_fields(parent, title, fields, ok_text=ok_text, accent=accent)
    if not values:
        return None
    return values.get("choice")


def confirm(parent, title: str, message: str, yes: str = "确定",
            no: str = "取消", danger: bool = False) -> bool:
    """暗色风格的确认对话框"""
    result = {"value": False}
    win, body = _modal_shell(parent, title, 400,
                             COLORS["danger"] if danger else COLORS["accent"])

    tk.Label(body, text=message, bg=COLORS["bg"], fg=COLORS["text"], font=font(10),
             justify="left", wraplength=340, anchor="w").pack(fill=tk.X, pady=(0, 14))

    def close(value):
        result["value"] = value
        _finish_modal(win)

    btns = tk.Frame(body, bg=COLORS["bg"])
    btns.pack(fill=tk.X)
    ttk.Button(btns, text=no, style="Ghost.TButton",
               command=lambda: close(False)).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btns, text=yes, style="Danger.TButton" if danger else "Accent.TButton",
               command=lambda: close(True)).pack(side=tk.RIGHT, padx=4)

    win.bind("<Escape>", lambda e: close(False))
    win.bind("<Return>", lambda e: close(True))
    win.protocol("WM_DELETE_WINDOW", lambda: close(False))
    center_window(win, 400, None, parent)
    try:
        win.grab_set()
        win.focus_force()
    except Exception:
        pass
    try:
        parent.wait_window(win)
    except Exception:
        pass
    return result["value"]
