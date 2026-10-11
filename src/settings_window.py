"""
设置窗口

- Notebook 分页：常规 / 截图 / 历史 / 快捷键 / 画笔 / 存储 / 关于
- 所有偏好本地保存（%APPDATA%/ScreenTool/settings.json），重启后保持
- 「保存并应用」会立即生效（热键重新注册、历史目录切换、主题色刷新）
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser

import app_settings as app_settings_mod
import ui_theme
from ui_theme import COLORS, font, toast, ScrollableFrame, CATEGORY_COLORS

APP_VERSION = app_settings_mod.APP_VERSION

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "ScreenTool"


# ════════════════════════════════════════════
# 开机自启（注册表）
# ════════════════════════════════════════════

def get_autostart() -> bool:
    """读取是否已设置开机自启"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            return bool(value)
    except Exception:
        return False


def set_autostart(enabled: bool) -> bool:
    """设置 / 取消开机自启，返回是否成功"""
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                exe = sys.executable if getattr(sys, "frozen", False) else \
                    f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                if getattr(sys, "frozen", False):
                    exe = f'"{sys.executable}"'
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, exe)
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


class SettingsWindow:
    """设置窗口"""

    def __init__(self, root: tk.Misc, settings, history=None, on_apply=None):
        self.root = root
        self.settings = settings
        self.history = history
        self.on_apply = on_apply

        self.win = None
        self._vars = {}
        self._getters = {}
        self._dirty = False

    # ════════════════════════════════
    # 显示 / 关闭
    # ════════════════════════════════

    def show(self):
        if self.win and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            try:
                self.win.focus_force()
            except Exception:
                pass
            self._load_values()
            self._refresh_storage_info()
            return

        self.win = tk.Toplevel(self.root)
        self.win.title("ScreenTool - 设置")
        self.win.geometry("760x640")
        self.win.minsize(660, 520)
        self.win.configure(bg=COLORS["bg"])
        try:
            ui_theme.glassify(self.win, self.settings)
        except Exception:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        try:
            ui_theme.apply(self.win, self.settings.get("accent"))
        except Exception:
            pass

        self._build_ui()
        self._load_values()
        self._refresh_storage_info()
        ui_theme.center_window(self.win)
        self.win.bind("<Escape>", lambda e: self.hide())
        try:
            self.win.focus_force()
        except Exception:
            pass

    def hide(self):
        if self.win and self.win.winfo_exists():
            self.win.destroy()
        self.win = None

    def set_status(self, text: str):
        """供外部更新底部状态文字"""
        try:
            if self._status:
                self._status.configure(text=text or "")
        except Exception:
            pass

    # ════════════════════════════════
    # 界面
    # ════════════════════════════════

    def _build_ui(self):
        header = tk.Frame(self.win, bg=COLORS["panel"], padx=16, pady=11)
        header.pack(fill=tk.X)
        tk.Label(header, text="⚙", bg=COLORS["panel"], fg=COLORS["accent"],
                 font=font(14, True)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(header, text="设置", bg=COLORS["panel"], fg=COLORS["text"],
                 font=font(14, True)).pack(side=tk.LEFT)
        tk.Label(header, text=f"v{APP_VERSION}　·　所有偏好保存在本地，重启后依然生效",
                 bg=COLORS["panel"], fg=COLORS["text_mute"], font=font(8)).pack(side=tk.LEFT, padx=12)

        self.notebook = ttk.Notebook(self.win)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self._build_tab_general()
        self._build_tab_capture()
        self._build_tab_history()
        self._build_tab_rope()
        self._build_tab_hotkeys()
        self._build_tab_brush()
        self._build_tab_storage()
        self._build_tab_about()

        footer = tk.Frame(self.win, bg=COLORS["panel"], padx=14, pady=10)
        footer.pack(fill=tk.X)
        self._status = tk.Label(footer, text="", bg=COLORS["panel"], fg=COLORS["text_dim"],
                                font=font(8))
        self._status.pack(side=tk.LEFT)

        ttk.Button(footer, text="关闭", style="Ghost.TButton",
                   command=self.hide).pack(side=tk.RIGHT, padx=4)
        ttk.Button(footer, text="恢复默认", style="TButton",
                   command=self._reset).pack(side=tk.RIGHT, padx=4)
        ttk.Button(footer, text="保存并应用", style="Accent.TButton",
                   command=self._save).pack(side=tk.RIGHT, padx=4)

    def _new_tab(self, title: str) -> tk.Frame:
        holder = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(holder, text=title)
        scroll = ScrollableFrame(holder, bg=COLORS["bg"])
        scroll.pack(fill=tk.BOTH, expand=True)
        body = tk.Frame(scroll.inner, bg=COLORS["bg"], padx=16, pady=14)
        body.pack(fill=tk.BOTH, expand=True)
        return body

    # ── 表单构造辅助 ──

    def _section(self, parent, title: str):
        box = tk.Frame(parent, bg=COLORS["bg"])
        box.pack(fill=tk.X, pady=(2, 10))
        tk.Label(box, text=title, bg=COLORS["bg"], fg=COLORS["accent"],
                 font=font(10, True), anchor="w").pack(fill=tk.X)
        line = tk.Frame(box, bg=COLORS["border"], height=1)
        line.pack(fill=tk.X, pady=(4, 8))
        return box

    def _row(self, parent, label: str, hint: str = None, key: str = None):
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill=tk.X, pady=4)
        left = tk.Frame(row, bg=COLORS["bg"], width=190)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        tk.Label(left, text=label, bg=COLORS["bg"], fg=COLORS["text"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        if hint:
            tk.Label(left, text=hint, bg=COLORS["bg"], fg=COLORS["text_mute"],
                     font=font(8), anchor="w", wraplength=180,
                     justify="left").pack(fill=tk.X)
        right = tk.Frame(row, bg=COLORS["bg"])
        right.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return right

    def _bool(self, parent, label: str, key: str, hint: str = None):
        right = self._row(parent, label, hint, key)
        var = tk.BooleanVar(value=bool(self.settings.get(key)))
        ttk.Checkbutton(right, text="启用", variable=var,
                        style="Panel.TCheckbutton").pack(side=tk.LEFT)
        self._vars[key] = var
        self._getters[key] = lambda v=var: bool(v.get())
        return var

    def _int(self, parent, label: str, key: str, from_=0, to=100000, hint: str = None,
             step: int = 1):
        right = self._row(parent, label, hint, key)
        var = tk.IntVar(value=int(self.settings.get(key) or 0))
        spin = ttk.Spinbox(right, from_=from_, to=to, increment=step, textvariable=var, width=10)
        spin.pack(side=tk.LEFT)
        self._vars[key] = var
        self._getters[key] = lambda v=var: int(v.get() or 0)
        return var

    def _text(self, parent, label: str, key: str, width: int = 32, hint: str = None):
        right = self._row(parent, label, hint, key)
        var = tk.StringVar(value=str(self.settings.get(key) or ""))
        ttk.Entry(right, textvariable=var, width=width).pack(side=tk.LEFT)
        self._vars[key] = var
        self._getters[key] = lambda v=var: (v.get() or "").strip()
        return var

    def _choice(self, parent, label: str, key: str, values: list, hint: str = None,
                readonly: bool = True):
        right = self._row(parent, label, hint, key)
        var = tk.StringVar(value=str(self.settings.get(key) or ""))
        box = ttk.Combobox(right, textvariable=var, values=values, width=22,
                           state="readonly" if readonly else "normal")
        box.pack(side=tk.LEFT)
        self._vars[key] = var
        self._getters[key] = lambda v=var: (v.get() or "").strip()
        return var

    def _float(self, parent, label: str, key: str, hint: str = None,
               from_=0.1, to=0.9):
        right = self._row(parent, label, hint, key)
        var = tk.DoubleVar(value=float(self.settings.get(key) or 0.4))
        scale = ttk.Scale(right, from_=from_, to=to, orient=tk.HORIZONTAL, length=180,
                          command=lambda v: var.set(round(float(v), 2)))
        scale.set(var.get())
        scale.pack(side=tk.LEFT)
        lbl = tk.Label(right, text=f"{var.get():.2f}", bg=COLORS["bg"], fg=COLORS["accent"],
                       font=ui_theme.mono(9), width=5)
        lbl.pack(side=tk.LEFT, padx=6)
        var.trace_add("write", lambda *a: _safe_config(lbl, text=f"{var.get():.2f}"))
        self._vars[key] = var
        self._getters[key] = lambda v=var: round(float(v.get()), 2)
        return var

    # ── 各分页 ──

    def _build_tab_general(self):
        body = self._new_tab("常规")
        sec = self._section(body, "启动与通知")
        self._autostart_var = tk.BooleanVar(value=get_autostart())
        right = self._row(sec, "开机自动启动", "写入当前用户注册表启动项")
        ttk.Checkbutton(right, text="启用", variable=self._autostart_var,
                        style="Panel.TCheckbutton").pack(side=tk.LEFT)
        self._bool(sec, "显示操作提示", "show_toast", "右下角浮层提示，截图/复制后可见")
        self._bool(sec, "结果面板置顶", "result_topmost", "截图结果窗口始终显示在最前")

        sec = self._section(body, "外观")
        self._choice(sec, "强调色", "accent", CATEGORY_COLORS,
                     "影响按钮、边框与高亮颜色")
        right = self._row(body, "自定义强调色", "从系统调色板中选择任意颜色")
        ttk.Button(right, text="选择颜色…", style="Ghost.TButton",
                   command=self._pick_accent).pack(side=tk.LEFT)
        self._int(sec, "历史窗口每行卡片数", "history_columns", 0, 6,
                  "0 = 根据窗口宽度自动排列", step=1)

        sec = self._section(body, "粘贴行为")
        self._bool(sec, "粘贴历史截图后恢复剪贴板", "restore_clipboard",
                   "自动 Ctrl+V 粘贴完成后，把剪贴板恢复为原来的内容")

    def _build_tab_capture(self):
        body = self._new_tab("截图")
        sec = self._section(body, "截图行为")
        self._bool(sec, "截图后自动复制到剪贴板", "auto_copy_image")
        self._bool(sec, "截图后弹出结果面板", "show_result_window")
        self._bool(sec, "框选时显示提示条", "capture_hint", "屏幕顶部显示快捷键说明")
        self._bool(sec, "框选时显示放大镜", "magnifier", "跟随鼠标放大显示像素与颜色")
        self._float(sec, "背景暗化程度", "dim_strength",
                    "数值越大，未被选中的区域越暗")

        sec = self._section(body, "文字识别（OCR）")
        self._bool(sec, "自动识别截图中的文字", "ocr_enabled")
        self._bool(sec, "把识别结果保存到历史记录", "ocr_save_to_history",
                   "之后可在历史窗口中搜索识别到的文字")
        self._int(sec, "最多提取的主色数量", "max_colors", 2, 16, step=1)

    def _build_tab_history(self):
        body = self._new_tab("历史记录")
        sec = self._section(body, "保存策略")
        self._bool(sec, "自动保存每张截图到本地", "save_history",
                   "关闭后截图不会写入历史记录")
        self._bool(sec, "自动生成标题", "auto_title", "用截图时间作为默认标题")
        self._int(sec, "最多保留记录数", "max_history", 0, 100000,
                  "0 = 不限制；超出后自动删除最旧的记录（收藏的记录不会被删）",
                  step=50)
        self._bool(sec, "删除前二次确认", "confirm_delete")

        sec = self._section(body, "分类管理")
        row = tk.Frame(sec, bg=COLORS["bg"])
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text="当前分类：" + "、".join(self.settings.category_list()),
                 bg=COLORS["bg"], fg=COLORS["text_dim"], font=font(9),
                 anchor="w").pack(side=tk.LEFT)
        ttk.Button(row, text="管理分类…", style="Ghost.TButton",
                   command=self._open_category_manager).pack(side=tk.RIGHT)
        tk.Label(sec, text="提示：删除或重命名分类时，可以同时把该分类下的截图迁移到其它分类。",
                 bg=COLORS["bg"], fg=COLORS["text_mute"], font=font(8),
                 anchor="w", justify="left").pack(fill=tk.X, pady=(2, 0))

    def _build_tab_rope(self):
        body = self._new_tab("绳子与特效")

        sec = self._section(body, "屏幕上的绳子（相片墙）")
        self._bool(sec, "启用绳子", "rope_enabled",
                   "截图后自动挂到屏幕顶部的绳子上，可拖动、可拖出粘贴")
        self._choice(sec, "绳子位置", "rope_position", ["top", "bottom"],
                     "top = 屏幕顶部 / bottom = 屏幕底部")
        self._int(sec, "条带高度（像素）", "rope_height", 120, 420,
                  "绳子上方留出的空间高度", step=10)
        self._int(sec, "最多挂几张", "rope_max_items", 3, 20,
                  "超出后最早的会从绳子上取下（不影响历史记录）", step=1)
        self._bool(sec, "无操作后自动收起", "rope_autohide",
                   "收起后只留一条发光细线，鼠标靠近自动展开")
        self._int(sec, "自动收起延迟（秒）", "rope_autohide_delay", 2, 60, None, step=1)
        self._bool(sec, "挂上后轻微摆动", "rope_swing", "相片像真的挂在绳子上一样晃动")

        sec = self._section(body, "拖动交互")
        self._bool(sec, "拖出绳子即粘贴", "rope_drag_paste",
                   "把相片拖离绳子并松手 → 自动粘贴到光标所在的应用窗口")
        self._bool(sec, "粘贴后从绳子取下", "rope_remove_after_paste",
                   "关掉则粘贴后继续挂在绳子上，方便反复使用")

        sec = self._section(body, "毛玻璃与特效")
        self._bool(sec, "启用毛玻璃背景", "glass_enabled",
                   "窗口背后的内容会被真实模糊（Windows 10 1803 及以上）")
        self._choice(sec, "玻璃模式", "glass_mode", ["blur", "acrylic"],
                     "blur 更平滑；acrylic 更亮，部分机器拖动会掉帧")
        self._float(sec, "窗口不透明度", "glass_alpha", "0.80 - 1.00", from_=0.80, to=1.0)
        self._text(sec, "玻璃染色", "glass_tint", 12, "十六进制颜色，如 #0B1020")
        self._int(sec, "染色浓度", "glass_tint_alpha", 0, 255,
                  "越大越暗、越不透明", step=8)

    def _build_tab_hotkeys(self):
        body = self._new_tab("快捷键")
        sec = self._section(body, "全局快捷键")
        self._text(sec, "截图", "hotkey_capture", 24, "默认 ctrl+alt+x")
        self._text(sec, "打开历史截图", "hotkey_history", 24, "默认 ctrl+alt+h")
        self._text(sec, "粘贴最近一张截图", "hotkey_paste_last", 24,
                   "默认 ctrl+alt+z（留空则关闭）")
        self._text(sec, "打开设置", "hotkey_settings", 24, "默认不注册，可留空")

        sec = self._section(body, "说明")
        for line in [
            "· 写法示例：ctrl+alt+x、ctrl+shift+s、f9、win+alt+p",
            "· 修改后点击「保存并应用」立即生效，无需重启软件",
            "· 若某个快捷键被其它软件占用，注册会失败并在提示中告知原快捷键",
            "· 框选过程中：拖拽选择区域 · 右键或 ESC 取消 · 回车 / 双击截取整个屏幕",
            "· 历史窗口：F5 刷新 · Ctrl+F 搜索 · 双击卡片查看大图",
            "· 画笔窗口：拖拽绘制 · 滚轮缩放 · 支持撤销 / 重做",
        ]:
            tk.Label(body, text=line, bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=font(9), anchor="w", justify="left").pack(fill=tk.X, pady=1)

    def _build_tab_brush(self):
        body = self._new_tab("画笔")
        brush = self.settings.get("brush") or {}

        sec = self._section(body, "默认工具")
        from paint_window import TOOLS
        tool_names = [t[1] for t in TOOLS]
        tool_map = dict((t[1], t[0]) for t in TOOLS)
        current_tool = brush.get("tool", "pen")
        right = self._row(sec, "默认工具", "打开画笔窗口时默认选中的工具")
        self._brush_tool_var = tk.StringVar(
            value=dict((t[0], t[1]) for t in TOOLS).get(current_tool, "画笔"))
        ttk.Combobox(right, textvariable=self._brush_tool_var, values=tool_names,
                     state="readonly", width=14).pack(side=tk.LEFT)
        self._brush_tool_map = tool_map

        right = self._row(sec, "默认颜色", "画笔初始颜色")
        self._brush_color_var = tk.StringVar(value=brush.get("color", "#FF3B30"))
        swatch = tk.Frame(right, bg=self._brush_color_var.get(), width=22, height=22,
                          highlightthickness=1, highlightbackground=COLORS["border"])
        swatch.pack(side=tk.LEFT, padx=(0, 8))
        swatch.pack_propagate(False)

        def pick_brush_color():
            rgb, hex_color = colorchooser.askcolor(color=self._brush_color_var.get(),
                                                   parent=self.win, title="选择画笔颜色")
            if hex_color:
                self._brush_color_var.set(str(hex_color).upper())
                _safe_config(swatch, bg=str(hex_color).upper())

        ttk.Button(right, text="选择颜色…", style="Ghost.TButton",
                   command=pick_brush_color).pack(side=tk.LEFT)

        self._brush_width_var = tk.IntVar(value=int(brush.get("width", 3) or 3))
        right = self._row(sec, "画笔粗细", "1 - 30（单位：图片像素）")
        ttk.Spinbox(right, from_=1, to=30, textvariable=self._brush_width_var,
                    width=8).pack(side=tk.LEFT)

        self._brush_text_var = tk.IntVar(value=int(brush.get("text_size", 20) or 20))
        right = self._row(sec, "文字工具字号", "10 - 120")
        ttk.Spinbox(right, from_=10, to=120, textvariable=self._brush_text_var,
                    width=8).pack(side=tk.LEFT)

        self._brush_mosaic_var = tk.IntVar(value=int(brush.get("mosaic_block", 12) or 12))
        right = self._row(sec, "马赛克颗粒大小", "3 - 40，数值越大越模糊")
        ttk.Spinbox(right, from_=3, to=40, textvariable=self._brush_mosaic_var,
                    width=8).pack(side=tk.LEFT)

        tk.Label(body, text="提示：画笔中的工具、颜色、粗细也会自动记住，重新打开时保持一致。",
                 bg=COLORS["bg"], fg=COLORS["text_mute"], font=font(8),
                 anchor="w", justify="left").pack(fill=tk.X, pady=(6, 0))

    def _build_tab_storage(self):
        body = self._new_tab("存储")
        sec = self._section(body, "位置")
        self._dir_label = tk.Label(sec, text="", bg=COLORS["bg"], fg=COLORS["text"],
                                   font=ui_theme.mono(8), anchor="w", justify="left",
                                   wraplength=460)
        self._dir_label.pack(fill=tk.X, pady=2)
        row = tk.Frame(sec, bg=COLORS["bg"])
        row.pack(fill=tk.X, pady=4)
        ttk.Button(row, text="打开数据目录", style="Ghost.TButton",
                   command=lambda: _open_path(app_settings_mod.data_dir())).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="打开历史截图目录", style="Ghost.TButton",
                   command=self._open_history_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="更改历史截图目录…", style="Ghost.TButton",
                   command=self._choose_history_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="恢复默认目录", style="Ghost.TButton",
                   command=self._reset_history_dir).pack(side=tk.LEFT, padx=2)

        sec = self._section(body, "占用统计")
        self._stat_label = tk.Label(sec, text="", bg=COLORS["bg"], fg=COLORS["text_dim"],
                                    font=font(9), anchor="w", justify="left")
        self._stat_label.pack(fill=tk.X, pady=2)

        sec = self._section(body, "备份与清理")
        row = tk.Frame(sec, bg=COLORS["bg"])
        row.pack(fill=tk.X, pady=4)
        ttk.Button(row, text="导出全部截图为 PNG…", style="Ghost.TButton",
                   command=self._export_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="导出索引 JSON…", style="Ghost.TButton",
                   command=self._export_index).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="清理索引中丢失的记录", style="Ghost.TButton",
                   command=self._clean_missing).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="清空全部历史记录", style="Danger.TButton",
                   command=self._clear_history).pack(side=tk.LEFT, padx=2)

        tk.Label(body, text="提示：历史记录默认保存在本机，不会上传到任何服务器；"
                            "删除记录会同时删除本地图片文件。",
                 bg=COLORS["bg"], fg=COLORS["text_mute"], font=font(8),
                 anchor="w", justify="left", wraplength=520).pack(fill=tk.X, pady=(8, 0))

    def _build_tab_about(self):
        body = self._new_tab("关于")
        tk.Label(body, text="ScreenTool　截屏工具箱", bg=COLORS["bg"], fg=COLORS["text"],
                 font=font(15, True), anchor="w").pack(fill=tk.X)
        tk.Label(body, text=f"版本 v{APP_VERSION}　·　暗色科技风界面　·　本地离线运行",
                 bg=COLORS["bg"], fg=COLORS["accent"], font=font(9),
                 anchor="w").pack(fill=tk.X, pady=(2, 12))

        features = [
            ("框选截图", "Ctrl+Alt+X 拖拽框选，支持多显示器，右键 / ESC 取消"),
            ("颜色提取", "自动提取截图主色，点击色块复制 HEX / RGB"),
            ("OCR 文字识别", "离线识别截图中的文字，保留排版，一键复制"),
            ("历史截图", "每张截图自动保存到本地，可命名、分类、标签、收藏、搜索、删除"),
            ("随时粘贴", "在历史窗口把任意一张历史截图复制到剪贴板，或自动 Ctrl+V 粘贴"),
            ("画笔批注", "画笔 / 荧光笔 / 直线 / 箭头 / 矩形 / 椭圆 / 文字 / 马赛克，支持撤销重做"),
            ("设置", "所有偏好本地保存，重启后保持；可关闭历史保存、修改快捷键与存储目录"),
        ]
        for name, desc in features:
            row = tk.Frame(body, bg=COLORS["card"], padx=12, pady=8)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=name, bg=COLORS["card"], fg=COLORS["accent"],
                     font=font(9, True), width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=desc, bg=COLORS["card"], fg=COLORS["text_dim"],
                     font=font(9), anchor="w", justify="left",
                     wraplength=420).pack(side=tk.LEFT)

        tk.Label(body, text="\n数据目录：" + app_settings_mod.data_dir(),
                 bg=COLORS["bg"], fg=COLORS["text_mute"], font=ui_theme.mono(8),
                 anchor="w", justify="left", wraplength=520).pack(fill=tk.X, pady=(10, 0))

    # ════════════════════════════════
    # 取值 / 保存
    # ════════════════════════════════

    def _load_values(self):
        """把设置文件里的值重新载入到界面控件"""
        for key, var in self._vars.items():
            try:
                value = self.settings.get(key)
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                elif isinstance(var, tk.IntVar):
                    var.set(int(value or 0))
                elif isinstance(var, tk.DoubleVar):
                    var.set(float(value or 0))
                else:
                    var.set("" if value is None else str(value))
            except Exception:
                pass
        try:
            self._autostart_var.set(get_autostart())
        except Exception:
            pass

    def _collect(self) -> dict:
        data = {}
        for key, getter in self._getters.items():
            try:
                data[key] = getter()
            except Exception:
                pass
        brush = self.settings.get("brush") or {}
        brush.update({
            "tool": self._brush_tool_map.get(self._brush_tool_var.get(), brush.get("tool", "pen")),
            "color": self._brush_color_var.get(),
            "width": int(self._brush_width_var.get() or 3),
            "text_size": int(self._brush_text_var.get() or 20),
            "mosaic_block": int(self._brush_mosaic_var.get() or 12),
        })
        data["brush"] = brush
        return data

    def _save(self):
        data = self._collect()

        # 校验快捷键格式
        for key, label in (("hotkey_capture", "截图"), ("hotkey_history", "历史截图"),
                           ("hotkey_paste_last", "粘贴最近一张"), ("hotkey_settings", "设置")):
            value = (data.get(key) or "").strip()
            if value and not _valid_hotkey(value):
                toast(self.win, "快捷键格式不正确", f"{label}：{value}", kind="error")
                return
        # 至少保留一个截图快捷键
        if not (data.get("hotkey_capture") or "").strip():
            toast(self.win, "「截图」快捷键不能为空", kind="error")
            return

        old_dir = self.settings.history_dir()
        self.settings.update(data, save=True)

        # 开机自启
        want_autostart = bool(self._autostart_var.get())
        if want_autostart != get_autostart():
            if not set_autostart(want_autostart):
                toast(self.win, "开机自启设置失败", "可能需要管理员权限", kind="warn")

        new_dir = self.settings.history_dir()
        if self.on_apply:
            try:
                self.on_apply(self.settings, {"old_history_dir": old_dir,
                                              "new_history_dir": new_dir})
            except Exception:
                pass

        self._status.configure(text="已保存并应用 ✓")
        toast(self.win, "设置已保存", "所有偏好已写入本地", kind="success")
        self._refresh_storage_info()
        try:
            ui_theme.apply(self.win, self.settings.get("accent"))
        except Exception:
            pass

    def _reset(self):
        if not ui_theme.confirm(self.win, "恢复默认设置",
                                "确定把全部偏好恢复为默认值吗？\n（历史截图与图片文件不会被删除）",
                                yes="恢复默认", danger=True):
            return
        self.settings.reset()
        self._load_values()
        brush = self.settings.get("brush") or {}
        self._brush_width_var.set(int(brush.get("width", 3)))
        self._brush_text_var.set(int(brush.get("text_size", 20)))
        self._brush_mosaic_var.set(int(brush.get("mosaic_block", 12)))
        self._brush_color_var.set(brush.get("color", "#FF3B30"))
        if self.on_apply:
            try:
                self.on_apply(self.settings, {})
            except Exception:
                pass
        toast(self.win, "已恢复默认设置", kind="success")

    # ════════════════════════════════
    # 存储相关操作
    # ════════════════════════════════

    def _refresh_storage_info(self):
        try:
            self._dir_label.configure(
                text=f"数据目录：{app_settings_mod.data_dir()}\n"
                     f"历史目录：{self.settings.history_dir()}\n"
                     f"设置文件：{self.settings.path}")
        except Exception:
            pass
        if self.history:
            stats = self.history.stats()
            try:
                self._stat_label.configure(
                    text=f"共 {stats['count']} 张截图　·　占用 "
                         f"{stats['bytes'] / 1024 / 1024:.1f} MB　·　"
                         f"收藏 {stats['pinned']} 张　·　"
                         f"文件缺失 {stats['missing']} 张\n"
                         + "分类：" + ("、".join(f"{k}({v})" for k, v in stats["categories"].items())
                                        or "（暂无）")
                )
            except Exception:
                pass

    def _open_history_dir(self):
        _open_path(self.settings.history_dir())

    def _choose_history_dir(self):
        path = filedialog.askdirectory(parent=self.win, title="选择历史截图保存目录",
                                       initialdir=self.settings.history_dir())
        if not path:
            return
        self.settings.set("history_dir", path, save=True)
        if self.on_apply:
            try:
                self.on_apply(self.settings, {})
            except Exception:
                pass
        self._refresh_storage_info()
        toast(self.win, "历史目录已更改", path, kind="success")

    def _reset_history_dir(self):
        self.settings.set("history_dir", "", save=True)
        if self.on_apply:
            try:
                self.on_apply(self.settings, {})
            except Exception:
                pass
        self._refresh_storage_info()
        toast(self.win, "已恢复默认目录", self.settings.history_dir(), kind="success")

    def _export_all(self):
        if not self.history or self.history.count() == 0:
            toast(self.win, "没有可导出的记录", kind="warn")
            return
        dest = filedialog.askdirectory(parent=self.win, title="选择导出目录")
        if not dest:
            return
        ids = [e["id"] for e in self.history.entries()]
        count = self.history.export_entries(ids, dest)
        toast(self.win, f"已导出 {count} 张截图", dest, kind="success")

    def _export_index(self):
        if not self.history:
            return
        path = filedialog.asksaveasfilename(parent=self.win, title="导出索引 JSON",
                                           defaultextension=".json",
                                           initialfile="screentool_history_index.json",
                                           filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        if self.history.export_index_json(path):
            toast(self.win, "索引已导出", os.path.basename(path), kind="success")
        else:
            toast(self.win, "导出失败", kind="error")

    def _clean_missing(self):
        if not self.history:
            return
        removed = self.history.mark_all_missing()
        self._refresh_storage_info()
        toast(self.win, f"已清理 {removed} 条无效记录", kind="success" if removed else "info")

    def _clear_history(self):
        if not self.history:
            return
        total = self.history.count()
        if total == 0:
            toast(self.win, "历史记录已经是空的", kind="warn")
            return
        if not ui_theme.confirm(self.win, "清空全部历史",
                                f"确定删除全部 {total} 条历史截图吗？\n此操作不可恢复。",
                                yes="全部删除", danger=True):
            return
        removed = self.history.clear_all()
        self._refresh_storage_info()
        toast(self.win, f"已清空 {removed} 条记录", kind="success")
        if self.on_apply:
            try:
                self.on_apply(self.settings, {})
            except Exception:
                pass

    def _pick_accent(self):
        rgb, hex_color = colorchooser.askcolor(color=self.settings.get("accent"),
                                               parent=self.win, title="选择强调色")
        if not hex_color:
            return
        hex_color = str(hex_color).upper()
        self.settings.set("accent", hex_color, save=True)
        if "accent" in self._vars:
            self._vars["accent"].set(hex_color)
        try:
            ui_theme.apply(self.win, hex_color)
        except Exception:
            pass
        if self.on_apply:
            try:
                self.on_apply(self.settings, {})
            except Exception:
                pass
        toast(self.win, "强调色已更新", hex_color, kind="success")

    def _open_category_manager(self):
        from history_window import CategoryManagerDialog

        def done():
            self._refresh_storage_info()
            if self.on_apply:
                try:
                    self.on_apply(self.settings, {})
                except Exception:
                    pass

        CategoryManagerDialog(self.win, self.settings, self.history, on_done=done)


# ════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════

def _valid_hotkey(value: str) -> bool:
    """简单校验快捷键写法"""
    value = (value or "").strip().lower()
    if not value:
        return False
    parts = [p.strip() for p in value.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return False
    modifiers = {"ctrl", "alt", "shift", "win", "cmd"}
    keys = [p for p in parts if p not in modifiers]
    if len(keys) != 1:
        return False
    key = keys[0]
    if len(key) == 1 and (key.isalnum() or key in "-=[];,./\\'`"):
        return True
    return key in {
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
        "space", "tab", "enter", "esc", "escape", "backspace", "delete", "insert",
        "home", "end", "page up", "page down", "up", "down", "left", "right",
        "print screen", "pause", "caps lock",
    }


def _safe_config(widget, **kwargs):
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def _open_path(path: str):
    try:
        os.makedirs(path, exist_ok=True)
        os.startfile(path)
    except Exception:
        pass
