"""
结果展示面板（暗色科技风 v2）

- 截图缩略图预览 + 尺寸/来源信息
- 色块列表（左键复制 HEX，右键复制 RGB）
- OCR 文字区域（可复制 / 可搜索）
- 一键：复制截图、画笔批注、保存到历史（可命名分类）、打开历史记录
"""

import datetime
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

import ui_theme
from ui_theme import COLORS, font, mono, toast
from clipboard_helper import copy_text, copy_image


class ResultWindow:
    """截图结果面板"""

    def __init__(self, root: tk.Misc, settings=None, history=None, callbacks: dict = None):
        self.root = root
        self.settings = settings
        self.history = history
        self.cb = callbacks or {}

        self.win = None
        self._image = None
        self._colors = []
        self._ocr_text = ""
        self._entry = None
        self._photo = None
        self._ocr_widget = None
        self._ocr_status = None
        self._saved_badge = None
        self._title_var = None
        self._category_var = None

    # ════════════════════════════════
    # 显示
    # ════════════════════════════════

    def show(self, screenshot: Image.Image, colors: list, ocr_text: str = "",
             entry: dict = None, source_text: str = "框选截图"):
        """
        显示结果面板

        Args:
            screenshot: 截图 PIL Image
            colors: [{"hex","rgb","pct"}, ...]
            ocr_text: OCR 文字（可先传「识别中…」）
            entry: 对应的历史记录（可为 None）
            source_text: 来源说明
        """
        if self.win and self.win.winfo_exists():
            try:
                self.win.destroy()
            except Exception:
                pass

        self._image = screenshot
        self._colors = colors or []
        self._ocr_text = ocr_text or ""
        self._entry = entry

        self.win = tk.Toplevel(self.root)
        self.win.title("ScreenTool - 截图结果")
        self.win.configure(bg=COLORS["bg"])
        try:
            ui_theme.glassify(self.win, self.settings)
        except Exception:
            pass
        self.win.resizable(True, True)
        topmost = True
        if self.settings is not None:
            topmost = bool(self.settings.get("result_topmost", True))
        try:
            self.win.attributes("-topmost", topmost)
        except Exception:
            pass
        try:
            ui_theme.apply(self.win, self.settings.get("accent") if self.settings else None)
        except Exception:
            pass

        self._build_ui(screenshot, source_text)
        self._set_ocr_widget_text(self._ocr_text)
        self.win.update_idletasks()
        ui_theme.center_window(self.win, offset_y=-40)
        self.win.bind("<Escape>", lambda e: self.close())
        try:
            self.win.focus_force()
        except Exception:
            pass

    def close(self):
        if self.win and self.win.winfo_exists():
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None

    def is_open(self) -> bool:
        return bool(self.win and self.win.winfo_exists())

    # ════════════════════════════════
    # 界面
    # ════════════════════════════════

    def _build_ui(self, screenshot: Image.Image, source_text: str):
        header = tk.Frame(self.win, bg=COLORS["panel"], padx=14, pady=10)
        header.pack(fill=tk.X)

        tk.Label(header, text="📷", bg=COLORS["panel"], fg=COLORS["accent"],
                 font=font(13, True)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(header, text="截图结果", bg=COLORS["panel"], fg=COLORS["text"],
                 font=font(13, True)).pack(side=tk.LEFT)

        self._saved_badge = tk.Label(header, text="", bg=COLORS["panel"],
                                     fg=COLORS["success"], font=font(9, True))
        self._saved_badge.pack(side=tk.LEFT, padx=10)
        if self._entry:
            self._saved_badge.configure(text="✓ 已保存到历史记录")
        elif self.history is not None:
            self._saved_badge.configure(text="未保存到历史", fg=COLORS["text_mute"])

        tk.Label(header, text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 bg=COLORS["panel"], fg=COLORS["text_mute"], font=mono(8)).pack(side=tk.RIGHT)

        body = tk.Frame(self.win, bg=COLORS["bg"], padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        columns = tk.Frame(body, bg=COLORS["bg"])
        columns.pack(fill=tk.BOTH, expand=True)

        # ── 左：预览 ──
        left = tk.Frame(columns, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        holder = tk.Frame(left, bg=COLORS["input"], highlightthickness=1,
                          highlightbackground=COLORS["border"])
        holder.pack(fill=tk.BOTH, expand=True)
        preview = screenshot.copy()
        preview.thumbnail((460, 340), Image.LANCZOS)
        try:
            self._photo = ImageTk.PhotoImage(preview)
            tk.Label(holder, image=self._photo, bg=COLORS["input"]).pack(expand=True, padx=4, pady=4)
        except Exception:
            tk.Label(holder, text="预览不可用", bg=COLORS["input"], fg=COLORS["text_mute"],
                     font=font(10)).pack(expand=True, pady=30)

        tk.Label(left, text=f"{screenshot.width} × {screenshot.height} px　·　{source_text}",
                 bg=COLORS["bg"], fg=COLORS["text_dim"], font=font(8),
                 anchor="w").pack(fill=tk.X, pady=(6, 0))

        # ── 右：颜色 + 命名 ──
        right = tk.Frame(columns, bg=COLORS["panel"], padx=12, pady=12, width=300)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        right.pack_propagate(False)

        tk.Label(right, text="主要颜色（左键复制 HEX · 右键复制 RGB）", bg=COLORS["panel"],
                 fg=COLORS["accent"], font=font(9, True), anchor="w").pack(fill=tk.X)
        colors_box = tk.Frame(right, bg=COLORS["panel"])
        colors_box.pack(fill=tk.X, pady=(6, 12))
        self._build_colors(colors_box)

        tk.Label(right, text="标题", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        self._title_var = tk.StringVar(value=(self._entry or {}).get("title", "") or "")
        ttk.Entry(right, textvariable=self._title_var).pack(fill=tk.X, pady=(4, 10))

        tk.Label(right, text="分类", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        cats = self.settings.category_list() if self.settings else ["默认"]
        self._category_var = tk.StringVar(
            value=(self._entry or {}).get("category") or (cats[0] if cats else "默认"))
        ttk.Combobox(right, textvariable=self._category_var, values=cats,
                     state="readonly").pack(fill=tk.X, pady=(4, 10))

        if self.history is not None:
            ttk.Button(right, text="保存标题与分类", style="Accent.TButton",
                       command=self._save_meta).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="复制截图到剪贴板", style="TButton",
                   command=self._on_copy_image).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="画笔批注", style="TButton",
                   command=self._on_paint).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="打开历史记录", style="TButton",
                   command=lambda: self._call("history")).pack(fill=tk.X, pady=2)

        # ── OCR 区域 ──
        ocr_frame = tk.Frame(body, bg=COLORS["panel"], padx=12, pady=10)
        ocr_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        ocr_head = tk.Frame(ocr_frame, bg=COLORS["panel"])
        ocr_head.pack(fill=tk.X)
        tk.Label(ocr_head, text="📝 识别的文字", bg=COLORS["panel"], fg=COLORS["accent"],
                 font=font(9, True)).pack(side=tk.LEFT)
        self._ocr_status = tk.Label(ocr_head, text="", bg=COLORS["panel"],
                                    fg=COLORS["text_mute"], font=font(8))
        self._ocr_status.pack(side=tk.LEFT, padx=8)

        ttk.Button(ocr_head, text="复制全部文字", style="CardGhost.TButton",
                   command=self._on_copy_text).pack(side=tk.RIGHT, padx=2)
        ttk.Button(ocr_head, text="复制截图", style="CardGhost.TButton",
                   command=self._on_copy_image).pack(side=tk.RIGHT, padx=2)

        text_holder = tk.Frame(ocr_frame, bg=COLORS["input"])
        text_holder.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self._ocr_widget = tk.Text(text_holder, height=7, wrap=tk.NONE,
                                   bg=COLORS["input"], fg=COLORS["text"],
                                   insertbackground=COLORS["accent"],
                                   relief=tk.FLAT, font=font(10), padx=8, pady=6,
                                   highlightthickness=1, highlightbackground=COLORS["border"])
        scroll_y = ttk.Scrollbar(text_holder, orient=tk.VERTICAL, command=self._ocr_widget.yview)
        scroll_x = ttk.Scrollbar(text_holder, orient=tk.HORIZONTAL, command=self._ocr_widget.xview)
        self._ocr_widget.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self._ocr_widget.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        text_holder.grid_rowconfigure(0, weight=1)
        text_holder.grid_columnconfigure(0, weight=1)

        # ── 底部按钮 ──
        footer = tk.Frame(self.win, bg=COLORS["bg"], padx=14, pady=10)
        footer.pack(fill=tk.X)
        hint = "提示：截图已复制到剪贴板，可直接 Ctrl+V 粘贴" if (
            self.settings is None or self.settings.get("auto_copy_image", True)
        ) else "提示：可在设置中开启「截图后自动复制到剪贴板」"
        tk.Label(footer, text=hint, bg=COLORS["bg"], fg=COLORS["text_mute"],
                 font=font(8)).pack(side=tk.LEFT)
        ttk.Button(footer, text="关闭", style="Ghost.TButton",
                   command=self.close).pack(side=tk.RIGHT, padx=3)
        if self.history is not None and not self._entry:
            ttk.Button(footer, text="保存到历史记录", style="Accent.TButton",
                       command=self._save_to_history).pack(side=tk.RIGHT, padx=3)

    def _build_colors(self, parent):
        if not self._colors:
            tk.Label(parent, text="（未提取到颜色）", bg=COLORS["panel"],
                     fg=COLORS["text_mute"], font=font(8)).pack(anchor="w")
            return

        row = None
        for index, color in enumerate(self._colors):
            if index % 4 == 0:
                row = tk.Frame(parent, bg=COLORS["panel"])
                row.pack(fill=tk.X, pady=2)
            self._make_swatch(row, color)

    def _make_swatch(self, parent, color: dict):
        holder = tk.Frame(parent, bg=COLORS["panel"], padx=2)
        holder.pack(side=tk.LEFT)
        swatch = tk.Frame(holder, bg=color["hex"], width=26, height=26,
                          highlightthickness=1, highlightbackground=COLORS["border"],
                          cursor="hand2")
        swatch.pack()
        swatch.pack_propagate(False)
        label = tk.Label(holder, text=color["hex"], bg=COLORS["panel"], fg=COLORS["text_dim"],
                         font=mono(7), cursor="hand2")
        label.pack()

        def copy_hex(_e=None, h=color["hex"]):
            if copy_text(h):
                toast(self.win, f"已复制 {h}", "HEX 颜色码", kind="success")

        def copy_rgb(_e=None, c=color):
            rgb = c.get("rgb") or ()
            text = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})" if len(rgb) >= 3 else str(rgb)
            if copy_text(text):
                toast(self.win, f"已复制 {text}", "RGB 颜色", kind="success")

        for w in (swatch, label):
            w.bind("<Button-1>", copy_hex)
            w.bind("<Button-3>", copy_rgb)

    # ════════════════════════════════
    # OCR 更新
    # ════════════════════════════════

    def set_ocr_text(self, text: str, status: str = "识别完成"):
        """异步 OCR 完成后由主线程调用"""
        self._ocr_text = text or ""
        self._set_ocr_widget_text(self._ocr_text)
        if self._entry and self.history is not None:
            try:
                self.history.attach_ocr(self._entry.get("id"), ocr_text=self._ocr_text)
            except Exception:
                pass
        self._call("on_ocr_done", self._ocr_text)

    def _set_ocr_widget_text(self, text: str):
        if not (self.win and self.win.winfo_exists() and self._ocr_widget):
            return
        try:
            self._ocr_widget.delete("1.0", tk.END)
            if text:
                self._ocr_widget.insert("1.0", text)
            else:
                self._ocr_widget.insert("1.0", "（未识别到文字）")
            self._ocr_widget.see("1.0")
        except Exception:
            return
        if self._ocr_status:
            try:
                if text.startswith("[OCR"):
                    self._ocr_status.configure(text=text[:60], fg=COLORS["warn"])
                elif text == "识别中…":
                    self._ocr_status.configure(text="正在识别文字…", fg=COLORS["text_mute"])
                elif not text:
                    self._ocr_status.configure(text="未识别到文字", fg=COLORS["text_mute"])
                else:
                    self._ocr_status.configure(text=f"共 {len(text)} 个字符", fg=COLORS["success"])
            except Exception:
                pass

    # ════════════════════════════════
    # 操作
    # ════════════════════════════════

    def _on_copy_text(self):
        text = ""
        if self._ocr_widget:
            try:
                text = self._ocr_widget.get("1.0", tk.END).strip()
            except Exception:
                text = self._ocr_text
        if not text or text.startswith("（未识别"):
            toast(self.win, "没有可复制的文字", kind="warn")
            return
        if copy_text(text):
            toast(self.win, "已复制文字到剪贴板", f"{len(text)} 个字符", kind="success")

    def _on_copy_image(self):
        if self._image is not None and copy_image(self._image):
            toast(self.win, "已复制截图到剪贴板", "可直接 Ctrl+V 粘贴", kind="success")
        else:
            toast(self.win, "复制失败", "请重试", kind="error")

    def _on_paint(self):
        handler = self.cb.get("paint")
        if handler:
            try:
                handler(self._image, self._entry)
                return
            except Exception as e:
                toast(self.win, "无法打开画笔", str(e), kind="error")
                return
        try:
            from paint_window import PaintWindow
            PaintWindow(self.root, self._image, self.settings, entry=self._entry,
                        history=self.history)
        except Exception as e:
            toast(self.win, "无法打开画笔", str(e), kind="error")

    def _save_meta(self):
        if self.history is None:
            return
        title = (self._title_var.get() or "").strip()
        category = (self._category_var.get() or "").strip() or "默认"
        if self.settings is not None:
            try:
                self.settings.add_category(category)
            except Exception:
                pass
        if self._entry:
            updated = self.history.update(self._entry.get("id"), title=title or "未命名截图",
                                         category=category)
            if updated:
                self._entry = updated
                toast(self.win, "已保存标题与分类", f"{title} · {category}", kind="success")
        else:
            self._save_to_history()
            return
        self._call("on_changed")

    def _save_to_history(self):
        if self.history is None or self._image is None:
            toast(self.win, "历史记录功能未启用", "可在设置中开启", kind="warn")
            return
        title = (self._title_var.get() or "").strip() if self._title_var else ""
        category = (self._category_var.get() or "").strip() if self._category_var else ""
        entry = self.history.add(self._image, title=title, category=category,
                                 ocr_text=self._ocr_text if
                                 (self.settings is None or self.settings.get("ocr_save_to_history", True))
                                 else "",
                                 colors=[c.get("hex") for c in self._colors],
                                 source="capture")
        if entry:
            self._entry = entry
            if self._saved_badge:
                self._saved_badge.configure(text="✓ 已保存到历史记录", fg=COLORS["success"])
            toast(self.win, "已保存到历史记录", entry.get("title", ""), kind="success")
            self._call("on_changed")
        else:
            toast(self.win, "保存失败", kind="error")

    # ════════════════════════════════
    # 回调
    # ════════════════════════════════

    def _call(self, name: str, *args):
        handler = self.cb.get(name)
        if handler:
            try:
                handler(*args)
            except Exception:
                pass
