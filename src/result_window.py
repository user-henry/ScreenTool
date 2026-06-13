"""
结果展示面板
- 截图缩略图预览
- 色块列表（点击复制 HEX）
- OCR 文字区域（可选复制）
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from PIL import Image, ImageTk

from clipboard_helper import copy_text, copy_image


class ResultWindow:
    """截图结果面板"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.win = None
        self._colors = []
        self._ocr_text = ""
        self._ocr_text_widget = None  # 引用 OCR Text 控件，供复制按钮实时读取

    def show(self, screenshot: Image.Image, colors: list, ocr_text: str):
        """
        显示结果面板

        Args:
            screenshot: 截图 PIL Image
            colors: 颜色列表 [{"hex":"#FF5733","rgb":(255,87,51),"pct":35.2}, ...]
            ocr_text: OCR 识别的文字（可能为空）
        """
        if self.win and self.win.winfo_exists():
            self.win.destroy()

        self._colors = colors
        self._ocr_text = ocr_text

        self.win = tk.Toplevel(self.root)
        self.win.title("ScreenTool - 截图结果")
        self.win.resizable(False, False)
        self.win.attributes('-topmost', True)

        # 设置窗口图标和样式
        self.win.configure(bg='#f5f5f5')

        main_frame = tk.Frame(self.win, bg='#f5f5f5', padx=14, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── 标题栏 ──
        title = tk.Label(
            main_frame, text="📷 截图结果",
            font=('Microsoft YaHei UI', 12, 'bold'),
            bg='#f5f5f5', fg='#333',
        )
        title.pack(anchor=tk.W, pady=(0, 8))

        # ── 截图预览 ──
        self._build_preview(main_frame, screenshot)

        # ── 颜色区域 ──
        self._build_colors(main_frame, colors)

        # ── OCR 文字区域 ──
        self._build_ocr(main_frame, ocr_text)

        # ── 底部按钮 ──
        btn_frame = tk.Frame(main_frame, bg='#f5f5f5')
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            btn_frame, text="复制截图",
            command=lambda: self._on_copy_image(screenshot),
        ).pack(side=tk.LEFT, padx=3)

        ttk.Button(
            btn_frame, text="关闭",
            command=self.win.destroy,
        ).pack(side=tk.RIGHT, padx=3)

        # 窗口居中
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2 - 50
        self.win.geometry(f"+{x}+{y}")

        self.win.focus_force()

    def _build_preview(self, parent, screenshot: Image.Image):
        """构建截图预览区域"""
        frame = tk.LabelFrame(
            parent, text="截图预览",
            font=('Microsoft YaHei UI', 9),
            bg='#f5f5f5', fg='#555',
            padx=6, pady=6,
        )
        frame.pack(fill=tk.X, pady=(0, 8))

        # 缩放到合适大小（最大宽度 400）
        img = screenshot.copy()
        w, h = img.size
        max_w = 400
        if w > max_w:
            ratio = max_w / w
            img = img.resize((max_w, int(h * ratio)), Image.LANCZOS)

        self._preview_tk = ImageTk.PhotoImage(img)
        lbl = tk.Label(frame, image=self._preview_tk, bg='#f5f5f5')
        lbl.pack()

        info = tk.Label(
            frame,
            text=f"尺寸: {screenshot.width} × {screenshot.height}  |  已复制到剪贴板",
            font=('Microsoft YaHei UI', 8),
            bg='#f5f5f5', fg='#888',
        )
        info.pack(pady=(4, 0))

    def _build_colors(self, parent, colors: list):
        """构建颜色色块区域"""
        if not colors:
            return

        frame = tk.LabelFrame(
            parent, text="🎨 主要颜色（点击复制 HEX）",
            font=('Microsoft YaHei UI', 9),
            bg='#f5f5f5', fg='#555',
            padx=6, pady=6,
        )
        frame.pack(fill=tk.X, pady=(0, 8))

        # 颜色容器（可换行）
        colors_frame = tk.Frame(frame, bg='#f5f5f5')
        colors_frame.pack(fill=tk.X)

        row_frame = None
        col_count = 0
        max_per_row = 6

        for i, color in enumerate(colors):
            if col_count == 0:
                row_frame = tk.Frame(colors_frame, bg='#f5f5f5')
                row_frame.pack(fill=tk.X, pady=2)

            self._make_color_swatch(row_frame, color)
            col_count += 1

            if col_count >= max_per_row:
                col_count = 0

    def _make_color_swatch(self, parent, color: dict):
        """创建单个色块"""
        swatch_frame = tk.Frame(
            parent, bg='#f5f5f5',
            padx=2, pady=1,
        )
        swatch_frame.pack(side=tk.LEFT)

        # 颜色方块
        color_box = tk.Frame(
            swatch_frame,
            width=32, height=32,
            bg=color["hex"],
            highlightbackground='#ccc',
            highlightthickness=1,
            cursor='hand2',
        )
        color_box.pack(side=tk.LEFT, padx=(0, 4))
        color_box.pack_propagate(False)

        # HEX 标签
        hex_label = tk.Label(
            swatch_frame,
            text=color["hex"],
            font=('Consolas', 9),
            bg='#f5f5f5', fg='#333',
            cursor='hand2',
        )
        hex_label.pack(side=tk.LEFT)

        # 百分比
        pct_label = tk.Label(
            swatch_frame,
            text=f" {color['pct']}%",
            font=('Microsoft YaHei UI', 7),
            bg='#f5f5f5', fg='#999',
        )
        pct_label.pack(side=tk.LEFT)

        # 绑定点击事件
        hex_val = color["hex"]
        color_box.bind("<Button-1>", lambda e, h=hex_val: self._on_copy_color(h))
        hex_label.bind("<Button-1>", lambda e, h=hex_val: self._on_copy_color(h))

    def _on_copy_color(self, hex_val: str):
        """点击色块复制 HEX 码"""
        copy_text(hex_val)
        # 短暂提示
        if self.win and self.win.winfo_exists():
            self.win.title(f"已复制 {hex_val}")

    def _build_ocr(self, parent, ocr_text: str):
        """构建 OCR 文字区域"""
        ocr_frame = tk.LabelFrame(
            parent, text="📝 识别的文字",
            font=('Microsoft YaHei UI', 9),
            bg='#f5f5f5', fg='#555',
            padx=6, pady=6,
        )
        ocr_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        if not ocr_text or ocr_text.startswith("[OCR"):
            lbl = tk.Label(
                ocr_frame,
                text=ocr_text if ocr_text else "未识别到文字",
                font=('Microsoft YaHei UI', 9),
                bg='#f5f5f5', fg='#999',
            )
            lbl.pack(pady=6)
            return

        # 文字显示区域（带滚动条）
        text_container = tk.Frame(ocr_frame, bg='#f5f5f5')
        text_container.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            text_container,
            font=('Microsoft YaHei UI', 10),
            wrap=tk.NONE,
            bg='white',
            fg='#333',
            relief=tk.FLAT,
            padx=8, pady=6,
            height=max(3, min(15, ocr_text.count('\n') + 2)),
            width=50,
        )
        text_widget.insert('1.0', ocr_text)
        text_widget.config(state=tk.DISABLED)

        # 滚动条
        scroll_y = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=text_widget.yview)
        scroll_x = ttk.Scrollbar(text_container, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        text_widget.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        text_container.grid_rowconfigure(0, weight=1)
        text_container.grid_columnconfigure(0, weight=1)

        # 保存 Text 控件引用，供 _on_copy_text 实时读取最新内容
        self._ocr_text_widget = text_widget

        # 复制文字按钮
        copy_btn = ttk.Button(
            ocr_frame,
            text="复制全部文字",
            command=self._on_copy_text,
        )
        copy_btn.pack(pady=(6, 0))

    def _on_copy_text(self):
        """复制 OCR 文字（从 Text 控件实时读取，避免闭包捕获过期值）"""
        text = ""
        if self._ocr_text_widget is not None:
            try:
                text = self._ocr_text_widget.get('1.0', tk.END).rstrip('\n')
            except Exception:
                text = self._ocr_text if self._ocr_text else ""
        if copy_text(text):
            if self.win and self.win.winfo_exists():
                self.win.title("已复制文字到剪贴板")

    def _on_copy_image(self, screenshot: Image.Image):
        """复制截图到剪贴板"""
        if copy_image(screenshot):
            if self.win and self.win.winfo_exists():
                self.win.title("已复制截图到剪贴板")
        else:
            messagebox.showinfo("提示", "复制截图失败，请重试")
