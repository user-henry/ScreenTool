"""
画笔批注窗口

- 直接在截图上做批注：画笔、荧光笔、直线、箭头、矩形、椭圆、文字、马赛克
- 支持撤销 / 重做 / 清空 / 调色 / 粗细 / 缩放
- 结果可保存为新历史记录、覆盖原记录或复制到剪贴板
"""

import math
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

from PIL import Image, ImageDraw, ImageTk, ImageFont

import ui_theme
from ui_theme import COLORS, font, toast
from clipboard_helper import copy_image


# 工具定义：(id, 显示名, 说明)
TOOLS = [
    ("pen", "画笔", "自由绘制"),
    ("highlighter", "荧光笔", "半透明高亮"),
    ("line", "直线", "拉一条直线"),
    ("arrow", "箭头", "指向某个位置"),
    ("rect", "矩形", "画矩形框"),
    ("ellipse", "椭圆", "画椭圆/圆圈"),
    ("text", "文字", "点击后输入文字"),
    ("mosaic", "马赛克", "涂抹遮挡敏感信息"),
]

DEFAULT_COLORS = ["#FF3B30", "#FFB020", "#35D07F", "#3DE1FF",
                  "#7C5CFF", "#FF7AD9", "#FFFFFF", "#000000"]

TOOL_NAMES = dict((t[0], t[1]) for t in TOOLS)
TOOL_TIPS = dict((t[0], t[2]) for t in TOOLS)

_font_cache = {}


def _load_font(size: int):
    """加载绘制文字用的字体（带缓存与回退）"""
    size = max(8, int(size))
    if size in _font_cache:
        return _font_cache[size]
    loaded = None
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"):
        try:
            loaded = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if loaded is None:
        try:
            loaded = ImageFont.load_default()
        except Exception:
            loaded = None
    _font_cache[size] = loaded
    return loaded


class PaintWindow:
    """画笔批注窗口"""

    def __init__(self, root: tk.Misc, image: Image.Image, settings,
                 title: str = "画笔批注", entry: dict = None,
                 history=None, on_saved=None):
        """
        Args:
            root: tkinter 根窗口
            image: 待批注的 PIL Image
            settings: AppSettings 实例
            title: 窗口标题
            entry: 关联的历史记录（用于「覆盖原记录」）
            history: HistoryManager 实例
            on_saved: 保存后的回调 (action, image, entry)
        """
        self.root = root
        self.settings = settings
        self.history = history
        self.entry = entry
        self.on_saved = on_saved

        self._base = image.convert("RGB") if image.mode != "RGB" else image.copy()
        self._ops = []
        self._redo = []
        self._tool = (settings.brush("tool", "pen") if settings else "pen") or "pen"
        self._color = (settings.brush("color", "#FF3B30") if settings else "#FF3B30") or "#FF3B30"
        self._width = int((settings.brush("width", 3) if settings else 3) or 3)
        self._text_size = int((settings.brush("text_size", 20) if settings else 20) or 20)
        self._mosaic_block = int((settings.brush("mosaic_block", 12) if settings else 12) or 12)
        self._zoom = 1.0
        self._scale = 1.0
        self._ox = 0
        self._oy = 0
        self._rendered = None
        self._photo = None
        self._drag = None
        self._preview_ids = []
        self._closed = False

        self.win = tk.Toplevel(root)
        self.win.title(f"ScreenTool - {title}")
        self.win.configure(bg=COLORS["bg"])
        try:
            ui_theme.glassify(self.win, settings)
        except Exception:
            pass
        self.win.geometry("1100x760")
        self.win.minsize(700, 500)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            ui_theme.apply(self.win, settings.get("accent") if settings else None)
        except Exception:
            pass

        self._build_ui(title)
        self._set_tool(self._tool, initial=True)
        self._set_color(self._color)
        self.win.after(40, self._redraw)
        ui_theme.center_window(self.win)
        try:
            self.win.focus_force()
        except Exception:
            pass

    # ════════════════════════════════
    # 界面
    # ════════════════════════════════

    def _build_ui(self, title: str):
        # ── 顶部工具栏 ──
        bar = tk.Frame(self.win, bg=COLORS["panel"], padx=10, pady=8)
        bar.pack(fill=tk.X)

        tk.Label(bar, text="🖌", bg=COLORS["panel"], fg=COLORS["accent"],
                 font=font(13, True)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(bar, text=title, bg=COLORS["panel"], fg=COLORS["text"],
                 font=font(11, True)).pack(side=tk.LEFT, padx=(0, 14))

        self._tool_buttons = {}
        tool_row = tk.Frame(bar, bg=COLORS["panel"])
        tool_row.pack(side=tk.LEFT)
        for tool_id, name, _tip in TOOLS:
            btn = ttk.Button(tool_row, text=name, style="Tool.TButton",
                             command=lambda t=tool_id: self._set_tool(t))
            btn.pack(side=tk.LEFT, padx=2)
            self._tool_buttons[tool_id] = btn

        # ── 第二行：颜色 / 粗细 / 撤销 / 缩放 ──
        bar2 = tk.Frame(self.win, bg=COLORS["bg_alt"], padx=10, pady=7)
        bar2.pack(fill=tk.X)

        tk.Label(bar2, text="颜色", bg=COLORS["bg_alt"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT, padx=(0, 6))

        self._swatches = {}
        sw_row = tk.Frame(bar2, bg=COLORS["bg_alt"])
        sw_row.pack(side=tk.LEFT)
        recent = (self.settings.brush("recent_colors", None) if self.settings else None) or []
        colors = []
        for c in list(recent) + DEFAULT_COLORS:
            if c and str(c).upper() not in [x.upper() for x in colors]:
                colors.append(str(c))
        for c in colors[:10]:
            sw = tk.Frame(sw_row, bg=c, width=20, height=20,
                          highlightthickness=2, highlightbackground=COLORS["border"],
                          cursor="hand2")
            sw.pack(side=tk.LEFT, padx=2)
            sw.pack_propagate(False)
            sw.bind("<Button-1>", lambda e, cc=c: self._set_color(cc))
            self._swatches[c.upper()] = sw

        ttk.Button(bar2, text="自定义…", style="Ghost.TButton",
                   command=self._pick_color).pack(side=tk.LEFT, padx=(8, 14))

        tk.Label(bar2, text="粗细", bg=COLORS["bg_alt"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT, padx=(0, 6))
        self._width_scale = ttk.Scale(bar2, from_=1, to=30, orient=tk.HORIZONTAL, length=120,
                                      command=self._on_width_change)
        self._width_scale.pack(side=tk.LEFT)
        self._width_scale.set(self._width)
        self._width_lbl = tk.Label(bar2, text=str(self._width), bg=COLORS["bg_alt"],
                                   fg=COLORS["accent"], font=ui_theme.mono(9, True), width=3)
        self._width_lbl.pack(side=tk.LEFT, padx=(6, 14))

        ttk.Button(bar2, text="撤销", style="Ghost.TButton",
                   command=self._undo).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar2, text="重做", style="Ghost.TButton",
                   command=self._redo_last).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar2, text="清空批注", style="Ghost.TButton",
                   command=self._clear_ops).pack(side=tk.LEFT, padx=2)

        ttk.Button(bar2, text="－", style="Ghost.TButton", width=3,
                   command=lambda: self._zoom_by(1 / 1.25)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bar2, text="＋", style="Ghost.TButton", width=3,
                   command=lambda: self._zoom_by(1.25)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bar2, text="适应窗口", style="Ghost.TButton",
                   command=self._zoom_fit).pack(side=tk.RIGHT, padx=2)
        self._zoom_lbl = tk.Label(bar2, text="100%", bg=COLORS["bg_alt"],
                                  fg=COLORS["text_dim"], font=ui_theme.mono(9), width=5)
        self._zoom_lbl.pack(side=tk.RIGHT, padx=6)

        # ── 画布 ──
        canvas_holder = tk.Frame(self.win, bg=COLORS["bg"])
        canvas_holder.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_holder, bg="#05070F", highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<MouseWheel>", self._on_wheel)

        # ── 底部保存栏 ──
        bottom = tk.Frame(self.win, bg=COLORS["panel"], padx=12, pady=10)
        bottom.pack(fill=tk.X)

        tk.Label(bottom, text="标题", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT)
        self._title_var = tk.StringVar(value=(self.entry or {}).get("title", "") or "")
        ttk.Entry(bottom, textvariable=self._title_var, width=24,
                  style="Card.TEntry").pack(side=tk.LEFT, padx=(6, 14))

        tk.Label(bottom, text="分类", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT)
        cats = self.settings.category_list() if self.settings else ["默认"]
        self._category_var = tk.StringVar(
            value=(self.entry or {}).get("category") or (cats[0] if cats else "默认"))
        ttk.Combobox(bottom, textvariable=self._category_var, values=cats,
                     width=12, state="readonly").pack(side=tk.LEFT, padx=6)

        ttk.Button(bottom, text="关闭", style="Ghost.TButton",
                   command=self._on_close).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bottom, text="复制结果", style="Ghost.TButton",
                   command=self._copy_result).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bottom, text="保存为新记录", style="Accent.TButton",
                   command=lambda: self._save("new")).pack(side=tk.RIGHT, padx=3)
        if self.entry and self.history:
            ttk.Button(bottom, text="覆盖原记录", style="TButton",
                       command=lambda: self._save("overwrite")).pack(side=tk.RIGHT, padx=3)

        # ── 状态栏 ──
        self._status = tk.Label(self.win, text="", bg=COLORS["bg"], fg=COLORS["text_mute"],
                                font=font(8), anchor="w")
        self._status.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._status.configure(text="提示：拖拽绘制 · 滚轮缩放 · 文字工具点击图片后输入内容")

    # ════════════════════════════════
    # 工具与颜色
    # ════════════════════════════════

    def _set_tool(self, tool: str, initial: bool = False):
        self._tool = tool
        for tool_id, btn in self._tool_buttons.items():
            try:
                btn.configure(style="ToolActive.TButton" if tool_id == tool else "Tool.TButton")
            except Exception:
                pass
        if not initial:
            self._remember()
        self._update_status()

    def _set_color(self, color: str):
        self._color = color
        for key, sw in self._swatches.items():
            try:
                sw.configure(highlightbackground=COLORS["accent"] if key == color.upper()
                             else COLORS["border"])
            except Exception:
                pass
        self._remember()

    def _pick_color(self):
        try:
            _rgb, hex_color = colorchooser.askcolor(color=self._color, parent=self.win,
                                                    title="选择颜色")
        except Exception:
            return
        if hex_color:
            self._set_color(str(hex_color).upper())

    def _on_width_change(self, value):
        try:
            self._width = max(1, int(float(value)))
        except Exception:
            return
        try:
            self._width_lbl.configure(text=str(self._width))
        except Exception:
            pass
        self._remember()

    def _remember(self):
        """记住画笔设置，下次打开保持一致"""
        if not self.settings:
            return
        try:
            recent = [self._color] + [str(c) for c in (self.settings.brush("recent_colors", []) or [])
                                      if str(c).upper() != self._color.upper()]
            self.settings.remember_brush(
                tool=self._tool, color=self._color, width=self._width,
                text_size=self._text_size, mosaic_block=self._mosaic_block,
                recent_colors=recent[:10],
            )
        except Exception:
            pass

    def _update_status(self):
        try:
            self._status.configure(
                text=f"当前工具：{TOOL_NAMES.get(self._tool, '')}（{TOOL_TIPS.get(self._tool, '')}）"
                     f"　·　已绘制 {len(self._ops)} 步　·　可撤销 {len(self._ops)} 步"
            )
        except Exception:
            pass

    # ════════════════════════════════
    # 缩放与重绘
    # ════════════════════════════════

    def _fit_scale(self) -> float:
        try:
            cw = max(50, self.canvas.winfo_width() - 16)
            ch = max(50, self.canvas.winfo_height() - 16)
        except Exception:
            cw, ch = 900, 600
        return min(cw / max(1, self._base.width), ch / max(1, self._base.height), 1.0)

    def _zoom_fit(self):
        self._zoom = 1.0
        self._redraw()

    def _zoom_by(self, factor: float):
        self._zoom = max(0.2, min(6.0, self._zoom * factor))
        self._redraw()

    def _on_wheel(self, event):
        delta = 1 if getattr(event, "delta", 0) > 0 else -1
        self._zoom_by(1.1 if delta > 0 else 1 / 1.1)

    def _render(self) -> Image.Image:
        """按操作列表重新渲染图片"""
        img = self._base.copy()
        for op in self._ops:
            try:
                img = self._apply_op(img, op)
            except Exception:
                pass
        return img

    def _apply_op(self, img: Image.Image, op: dict) -> Image.Image:
        tool = op.get("tool")
        color = op.get("color", "#FF3B30")
        width = max(1, int(op.get("width", 3)))

        if tool in ("pen", "highlighter"):
            points = op.get("points") or []
            if len(points) < 2:
                return img
            if tool == "highlighter":
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                d.line(points, fill=_rgba(color, 90), width=max(8, width * 5), joint="curve")
                r = max(4, width * 2)
                for p in (points[0], points[-1]):
                    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=_rgba(color, 90))
                return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
            d.line(points, fill=color, width=width, joint="curve")
            r = max(1, width // 2)
            for p in (points[0], points[-1]):
                d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)
            return img

        if tool in ("line", "arrow"):
            start, end = op.get("start"), op.get("end")
            if not start or not end:
                return img
            d = ImageDraw.Draw(img)
            if tool == "arrow":
                _draw_arrow_head(d, start, end, color, width)
            d.line([start, end], fill=color, width=width)
            return img

        if tool in ("rect", "ellipse"):
            start, end = op.get("start"), op.get("end")
            if not start or not end:
                return img
            box = _normalize_box(start, end)
            d = ImageDraw.Draw(img)
            if tool == "rect":
                d.rectangle(box, outline=color, width=width)
            else:
                d.ellipse(box, outline=color, width=width)
            return img

        if tool == "text":
            pos, text = op.get("start"), op.get("text", "")
            if not pos or not text:
                return img
            d = ImageDraw.Draw(img)
            fnt = _load_font(op.get("size", 20))
            if fnt is None:
                return img
            x, y = pos
            size = int(op.get("size", 20))
            line_h = max(14, int(size * 1.3))
            stroke = _contrast(color)
            for i, line in enumerate(text.split("\n")):
                d.text((x, y + i * line_h), line, font=fnt, fill=color,
                       stroke_width=max(1, size // 14), stroke_fill=stroke)
            return img

        if tool == "mosaic":
            start, end = op.get("start"), op.get("end")
            if not start or not end:
                return img
            x1, y1, x2, y2 = _normalize_box(start, end)
            box = (max(0, x1), max(0, y1), min(img.width, x2), min(img.height, y2))
            if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                return img
            block = max(3, int(op.get("block", 12)))
            region = img.crop(box)
            small = region.resize((max(1, region.width // block), max(1, region.height // block)),
                                  Image.NEAREST)
            img.paste(small.resize(region.size, Image.NEAREST), (box[0], box[1]))
            return img

        return img

    def _redraw(self):
        """重新渲染并显示到画布"""
        if self._closed:
            return
        try:
            self._rendered = self._render()
        except Exception:
            return

        self._scale = self._fit_scale() * self._zoom
        dw = max(1, int(self._rendered.width * self._scale))
        dh = max(1, int(self._rendered.height * self._scale))
        try:
            disp = self._rendered.resize((dw, dh), Image.LANCZOS) \
                if (dw, dh) != self._rendered.size else self._rendered
            self._photo = ImageTk.PhotoImage(disp)
        except Exception:
            return

        try:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
        except Exception:
            cw, ch = dw, dh
        self._ox = max(0, (cw - dw) // 2)
        self._oy = max(0, (ch - dh) // 2)

        self.canvas.delete("all")
        self.canvas.create_image(self._ox, self._oy, anchor=tk.NW, image=self._photo)
        self.canvas.create_rectangle(self._ox, self._oy, self._ox + dw, self._oy + dh,
                                     outline=COLORS["border_light"])
        if self._drag:
            self._draw_preview()
        try:
            self._zoom_lbl.configure(text=f"{int(self._scale * 100)}%")
        except Exception:
            pass
        self._update_status()

    # ════════════════════════════════
    # 坐标换算
    # ════════════════════════════════

    def _to_image(self, cx, cy):
        return (int(round((cx - self._ox) / max(0.01, self._scale))),
                int(round((cy - self._oy) / max(0.01, self._scale))))

    def _to_canvas(self, ix, iy):
        return (self._ox + ix * self._scale, self._oy + iy * self._scale)

    def _clamp(self, point):
        return (max(0, min(self._base.width, point[0])),
                max(0, min(self._base.height, point[1])))

    # ════════════════════════════════
    # 绘制交互
    # ════════════════════════════════

    def _on_press(self, event):
        if self._closed:
            return
        pos = self._clamp(self._to_image(event.x, event.y))

        if self._tool == "text":
            self._ask_text(pos)
            return

        self._drag = {
            "tool": self._tool,
            "color": self._color,
            "width": self._width,
            "start": pos,
            "end": pos,
            "points": [pos],
            "block": self._mosaic_block,
        }
        self._clear_preview()

    def _on_motion(self, event):
        if not self._drag:
            return
        pos = self._clamp(self._to_image(event.x, event.y))
        self._drag["end"] = pos
        if self._drag["tool"] in ("pen", "highlighter"):
            self._drag["points"].append(pos)
        self._draw_preview()

    def _on_release(self, event):
        if not self._drag:
            return
        op = self._drag
        self._drag = None
        self._clear_preview()

        tool = op["tool"]
        if tool in ("pen", "highlighter"):
            valid = len(op["points"]) >= 2
            if valid:
                op["points"] = _simplify(op["points"])
        else:
            sx, sy = op["start"]
            ex, ey = op["end"]
            valid = abs(ex - sx) >= 2 or abs(ey - sy) >= 2

        if not valid:
            self._update_status()
            return

        self._ops.append(op)
        if len(self._ops) > 300:
            self._ops = self._ops[-300:]
        self._redo.clear()
        self._remember()
        self._redraw()

    def _clear_preview(self):
        for item in self._preview_ids:
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self._preview_ids = []

    def _draw_preview(self):
        """在画布上实时预览当前正在绘制的操作"""
        if not self._drag:
            return
        self._clear_preview()
        op = self._drag
        tool = op["tool"]
        color = op["color"]
        w = max(1, int(op["width"] * self._scale))
        px, py = self._to_canvas(*op["start"])
        ex, ey = self._to_canvas(*op["end"])

        try:
            if tool in ("pen", "highlighter"):
                pts = []
                for p in op["points"]:
                    pts.extend(self._to_canvas(*p))
                if len(pts) >= 4:
                    width_px = max(2, int(op["width"] * self._scale *
                                          (5 if tool == "highlighter" else 1)))
                    self._preview_ids.append(self.canvas.create_line(
                        *pts, fill=color, width=width_px, capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    ))
            elif tool == "line":
                self._preview_ids.append(self.canvas.create_line(
                    px, py, ex, ey, fill=color, width=w, capstyle=tk.ROUND))
            elif tool == "arrow":
                self._preview_ids.append(self.canvas.create_line(px, py, ex, ey, fill=color, width=w))
                self._preview_ids.append(self.canvas.create_polygon(
                    _arrow_head_canvas(px, py, ex, ey, w), fill=color, outline=color))
            elif tool == "rect":
                self._preview_ids.append(self.canvas.create_rectangle(
                    px, py, ex, ey, outline=color, width=w))
            elif tool == "ellipse":
                self._preview_ids.append(self.canvas.create_oval(
                    px, py, ex, ey, outline=color, width=w))
            elif tool == "mosaic":
                self._preview_ids.append(self.canvas.create_rectangle(
                    px, py, ex, ey, outline=COLORS["accent"], width=1, dash=(4, 3)))
                self._preview_ids.append(self.canvas.create_text(
                    (px + ex) / 2, (py + ey) / 2, text="马赛克",
                    fill=COLORS["accent"], font=font(9, True)))
        except Exception:
            pass

    def _ask_text(self, pos):
        """弹出文字输入框并在点击处写入文字"""
        text = ui_theme.prompt_text(
            self.win, "添加文字", label="输入要批注的文字（支持多行）",
            multiline=True,
            accent=self.settings.get("accent") if self.settings else None,
        )
        if not text:
            return
        self._ops.append({
            "tool": "text", "color": self._color, "width": self._width,
            "start": self._clamp(pos), "text": text, "size": self._text_size,
        })
        self._redo.clear()
        self._redraw()

    # ════════════════════════════════
    # 撤销 / 重做
    # ════════════════════════════════

    def _undo(self):
        if not self._ops:
            toast(self.win, "没有可撤销的操作", kind="warn")
            return
        self._redo.append(self._ops.pop())
        self._redraw()

    def _redo_last(self):
        if not self._redo:
            toast(self.win, "没有可重做的操作", kind="warn")
            return
        self._ops.append(self._redo.pop())
        self._redraw()

    def _clear_ops(self):
        if not self._ops:
            return
        if messagebox.askyesno("确认", "确定要清空所有批注吗？", parent=self.win):
            self._redo = list(self._ops) + self._redo
            self._ops = []
            self._redraw()

    # ════════════════════════════════
    # 输出
    # ════════════════════════════════

    def result_image(self) -> Image.Image:
        return self._render()

    def _copy_result(self):
        img = self.result_image()
        if copy_image(img):
            toast(self.win, "已复制批注结果到剪贴板", "可直接 Ctrl+V 粘贴", kind="success")
        else:
            toast(self.win, "复制失败", "请重试", kind="error")

    def _save(self, mode: str):
        img = self.result_image()
        title = (self._title_var.get() or "").strip()
        category = (self._category_var.get() or "").strip()

        if mode == "overwrite" and self.entry and self.history:
            if not messagebox.askyesno("确认覆盖", "确定用批注结果覆盖原记录吗？\n（原图无法恢复）",
                                       parent=self.win):
                return
            updated = self.history.replace_image(self.entry["id"], img)
            if updated:
                toast(self.win, "已覆盖原记录", updated.get("title", ""), kind="success")
                if self.on_saved:
                    try:
                        self.on_saved("overwrite", img, updated)
                    except Exception:
                        pass
                self.entry = updated
            else:
                toast(self.win, "覆盖失败", kind="error")
            return

        if not self.history:
            if copy_image(img):
                toast(self.win, "已复制批注结果", "历史记录未启用", kind="warn")
            return

        if not title:
            base_title = (self.entry or {}).get("title") or "截图"
            title = f"{base_title} (批注)"
        entry = self.history.add(img, title=title, category=category, source="paint")
        if entry:
            toast(self.win, "已保存到历史记录", entry.get("title", ""), kind="success")
            if self.on_saved:
                try:
                    self.on_saved("new", img, entry)
                except Exception:
                    pass
            self.entry = entry
            try:
                self._title_var.set(entry.get("title", ""))
            except Exception:
                pass
        else:
            toast(self.win, "保存失败", kind="error")

    def _on_close(self):
        if self._ops:
            try:
                if not messagebox.askyesno("确认关闭", "批注尚未保存，确定关闭吗？", parent=self.win):
                    return
            except Exception:
                pass
        self._closed = True
        self._remember()
        try:
            self.win.destroy()
        except Exception:
            pass


# ════════════════════════════════
# 绘制辅助
# ════════════════════════════════

def _rgba(color: str, alpha: int):
    """#RRGGBB → (r,g,b,alpha)"""
    try:
        c = str(color).lstrip("#")
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16),
                max(0, min(255, alpha)))
    except Exception:
        return (255, 255, 0, alpha)


def _contrast(color: str) -> str:
    """根据颜色亮度返回描边色（保证文字可读）"""
    try:
        c = str(color).lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#000000" if luminance > 0.55 else "#FFFFFF"
    except Exception:
        return "#000000"


def _normalize_box(start, end):
    x1, y1 = start
    x2, y2 = end
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _draw_arrow_head(draw, start, end, color, width):
    """在 PIL 图像上绘制箭头头部"""
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1:
        return
    head = max(12, width * 4)
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (x2 + head * math.cos(angle + math.radians(150)),
            y2 + head * math.sin(angle + math.radians(150)))
    right = (x2 + head * math.cos(angle - math.radians(150)),
             y2 + head * math.sin(angle - math.radians(150)))
    try:
        draw.polygon([(x2, y2), left, right], fill=color)
    except Exception:
        pass


def _arrow_head_canvas(px, py, ex, ey, width):
    """画布预览用箭头三角点列表"""
    length = math.hypot(ex - px, ey - py)
    if length < 1:
        return [ex, ey, ex, ey, ex, ey]
    head = max(10, width * 4)
    angle = math.atan2(ey - py, ex - px)
    left = (ex + head * math.cos(angle + math.radians(155)),
            ey + head * math.sin(angle + math.radians(155)))
    right = (ex + head * math.cos(angle - math.radians(155)),
             ey + head * math.sin(angle - math.radians(155)))
    return [ex, ey, left[0], left[1], right[0], right[1]]


def _simplify(points, min_dist: int = 2):
    """抽稀点集，避免存储过多坐标"""
    if len(points) <= 2:
        return list(points)
    out = [points[0]]
    for p in points[1:-1]:
        last = out[-1]
        if abs(p[0] - last[0]) + abs(p[1] - last[1]) >= min_dist:
            out.append(p)
    out.append(points[-1])
    return out
