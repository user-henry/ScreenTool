"""
历史截图窗口

- 缩略图卡片网格，支持搜索、分类筛选、排序、收藏
- 每张卡片可直接：粘贴（复制到剪贴板/自动 Ctrl+V）、画笔批注、命名、分类、收藏、删除、导出
- 支持多选批量删除 / 导出，支持从文件导入图片
"""

import os
import datetime
import tkinter as tk
from tkinter import ttk, filedialog

from PIL import Image, ImageTk

import ui_theme
from ui_theme import COLORS, font, toast, ScrollableFrame, Chip, CardContainer

CARD_WIDTH = 236
THUMB_BOX = (220, 150)
PAGE_SIZE = 60


def _fmt_size(num_bytes: int) -> str:
    try:
        num_bytes = float(num_bytes or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if num_bytes < 1024 or unit == "GB":
                return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
    except Exception:
        pass
    return "-"


def _fmt_time(iso_str: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str or "-"


def _short(text: str, limit: int) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def bind_tree(widget, handler, double_handler=None, skip_buttons=True):
    """递归给控件树绑定点击事件（跳过按钮，避免抢走按钮点击）"""
    targets = [widget]
    for child in widget.winfo_children():
        if skip_buttons and isinstance(child, (ttk.Button, tk.Button)):
            continue
        targets.extend(bind_tree(child, handler, double_handler, skip_buttons))
    for target in targets:
        try:
            target.bind("<Button-1>", handler)
            if double_handler:
                target.bind("<Double-Button-1>", double_handler)
            target.configure(cursor="hand2")
        except Exception:
            pass
    return targets


class HistoryWindow:
    """历史截图浏览窗口"""

    def __init__(self, root: tk.Misc, settings, history, callbacks: dict = None):
        self.root = root
        self.settings = settings
        self.history = history
        self.cb = callbacks or {}

        self.win = None
        self._thumbs = []
        self._cards = {}
        self._selected = set()
        self._filter_category = "全部"
        self._query = ""
        self._sort = "newest"
        self._limit = PAGE_SIZE
        self._preview = None

    # ════════════════════════════════
    # 显示 / 关闭
    # ════════════════════════════════

    def show(self, category: str = None, query: str = None):
        if self.win and self.win.winfo_exists():
            if category is not None:
                self._filter_category = category
                self._limit = PAGE_SIZE
            if query is not None:
                self._query = query
            self.win.deiconify()
            self.win.lift()
            try:
                self.win.focus_force()
            except Exception:
                pass
            self.refresh()
            return

        if category is not None:
            self._filter_category = category
        if query is not None:
            self._query = query

        self.win = tk.Toplevel(self.root)
        self.win.title("ScreenTool - 历史截图")
        self.win.geometry("1020x720")
        self.win.minsize(720, 520)
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
        self.refresh()
        ui_theme.center_window(self.win)
        self.win.bind("<Escape>", lambda e: self.hide())
        self.win.bind("<F5>", lambda e: self.refresh())
        self.win.bind("<Control-f>", lambda e: self._search_entry.focus_set())
        try:
            self.win.focus_force()
        except Exception:
            pass

    def hide(self):
        if self.win and self.win.winfo_exists():
            self.win.destroy()
        self.win = None
        self._thumbs = []
        self._cards = {}
        self._preview = None
        callback = self.cb.get("on_close")
        if callback:
            try:
                callback()
            except Exception:
                pass

    # ════════════════════════════════
    # 界面构建
    # ════════════════════════════════

    def _build_ui(self):
        # ── 顶部标题 + 搜索 ──
        header = tk.Frame(self.win, bg=COLORS["panel"], padx=14, pady=10)
        header.pack(fill=tk.X)

        tk.Label(header, text="🗂", bg=COLORS["panel"], fg=COLORS["accent"],
                 font=font(14, True)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(header, text="历史截图", bg=COLORS["panel"], fg=COLORS["text"],
                 font=font(14, True)).pack(side=tk.LEFT)

        self._count_badge = tk.Label(header, text="", bg=COLORS["card"], fg=COLORS["accent"],
                                     font=font(9, True), padx=8, pady=2)
        self._count_badge.pack(side=tk.LEFT, padx=10)

        ttk.Button(header, text="关闭", style="Ghost.TButton",
                   command=self.hide).pack(side=tk.RIGHT, padx=3)
        ttk.Button(header, text="设置", style="Ghost.TButton",
                   command=lambda: self._call("settings")).pack(side=tk.RIGHT, padx=3)
        ttk.Button(header, text="导入图片…", style="Ghost.TButton",
                   command=self._import_files).pack(side=tk.RIGHT, padx=3)
        ttk.Button(header, text="刷新", style="Ghost.TButton",
                   command=self.refresh).pack(side=tk.RIGHT, padx=3)

        # 搜索 + 排序
        search_row = tk.Frame(self.win, bg=COLORS["bg_alt"], padx=14, pady=8)
        search_row.pack(fill=tk.X)

        tk.Label(search_row, text="🔍", bg=COLORS["bg_alt"], fg=COLORS["text_dim"],
                 font=font(10)).pack(side=tk.LEFT, padx=(0, 6))
        self._search_var = tk.StringVar(value=self._query)
        self._search_entry = ttk.Entry(search_row, textvariable=self._search_var, width=34)
        self._search_entry.pack(side=tk.LEFT)
        self._search_entry.bind("<Return>", lambda e: self._apply_search())
        self._search_var.trace_add("write", lambda *a: self._apply_search())
        ttk.Button(search_row, text="清除", style="Ghost.TButton",
                   command=self._clear_search).pack(side=tk.LEFT, padx=6)

        tk.Label(search_row, text="排序", bg=COLORS["bg_alt"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT, padx=(16, 6))
        self._sort_var = tk.StringVar(value="最新优先")
        sort_box = ttk.Combobox(search_row, textvariable=self._sort_var, width=12,
                                state="readonly",
                                values=["最新优先", "最早优先", "标题", "文件大小"])
        sort_box.pack(side=tk.LEFT)
        sort_box.bind("<<ComboboxSelected>>", lambda e: self._on_sort())

        # ── 分类筛选 ──
        self._filter_row = tk.Frame(self.win, bg=COLORS["bg"], padx=14, pady=8)
        self._filter_row.pack(fill=tk.X)

        # ── 批量操作栏 ──
        self._action_row = tk.Frame(self.win, bg=COLORS["bg"], padx=14)
        self._action_row.pack(fill=tk.X)

        self._sel_label = tk.Label(self._action_row, text="未选择", bg=COLORS["bg"],
                                   fg=COLORS["text_dim"], font=font(9))
        self._sel_label.pack(side=tk.LEFT)

        self._btn_sel_all = ttk.Button(self._action_row, text="全选", style="CardGhost.TButton",
                                       command=self._select_all)
        self._btn_sel_all.pack(side=tk.LEFT, padx=6)
        self._btn_sel_none = ttk.Button(self._action_row, text="取消选择", style="CardGhost.TButton",
                                        command=self._clear_selection)
        self._btn_sel_none.pack(side=tk.LEFT, padx=(0, 12))

        self._btn_batch_paste = ttk.Button(self._action_row, text="批量导出", style="CardGhost.TButton",
                                           command=self._export_selected)
        self._btn_batch_paste.pack(side=tk.LEFT, padx=3)
        self._btn_batch_delete = ttk.Button(self._action_row, text="批量删除", style="CardGhost.TButton",
                                            command=self._delete_selected)
        self._btn_batch_delete.pack(side=tk.LEFT, padx=3)
        ttk.Button(self._action_row, text="清空全部历史", style="CardGhost.TButton",
                   command=self._clear_all).pack(side=tk.RIGHT, padx=3)
        ttk.Button(self._action_row, text="管理分类", style="CardGhost.TButton",
                   command=self._manage_categories).pack(side=tk.RIGHT, padx=3)
        ttk.Button(self._action_row, text="打开存储目录", style="CardGhost.TButton",
                   command=self._open_storage_dir).pack(side=tk.RIGHT, padx=3)

        # ── 卡片网格 ──
        self._scroll = ScrollableFrame(self.win, bg=COLORS["bg"])
        self._scroll.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 4))

        # ── 底部状态 ──
        footer = tk.Frame(self.win, bg=COLORS["panel"], padx=14, pady=7)
        footer.pack(fill=tk.X)
        self._status = tk.Label(footer, text="", bg=COLORS["panel"], fg=COLORS["text_dim"],
                                font=font(8), anchor="w")
        self._status.pack(side=tk.LEFT)
        self._more_btn = ttk.Button(footer, text="加载更多", style="Ghost.TButton",
                                    command=self._load_more)
        self._more_btn.pack(side=tk.RIGHT)

    # ════════════════════════════════
    # 数据刷新
    # ════════════════════════════════

    def _sort_key(self) -> str:
        return {
            "最新优先": "newest", "最早优先": "oldest",
            "标题": "title", "文件大小": "size",
        }.get(self._sort_var.get(), "newest")

    def _current_entries(self) -> list:
        return self.history.entries(category=self._filter_category,
                                    query=self._query, sort=self._sort_key())

    def refresh(self):
        """重建分类筛选条与卡片网格"""
        if not self.win or not self.win.winfo_exists():
            return
        self._rebuild_filters()
        self._rebuild_cards()

    def _rebuild_filters(self):
        for child in self._filter_row.winfo_children():
            child.destroy()

        stats = self.history.categories_in_use()
        total = sum(stats.values())
        options = [("全部", total), ("★ 收藏", stats_pinned(self.history))]
        for name in self.settings.category_list():
            options.append((name, stats.get(name, 0)))
        for name, count in stats.items():
            if name not in [o[0] for o in options]:
                options.append((name, count))

        tk.Label(self._filter_row, text="分类", bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=font(9)).pack(side=tk.LEFT, padx=(0, 8))

        for name, count in options:
            if name != "全部" and count == 0 and name not in ("★ 收藏",):
                continue
            label = f"{name} {count}" if count else name
            chip = Chip(self._filter_row, label, color=ui_theme.category_color(name),
                        on_click=lambda n=name: self._set_filter(n),
                        active=(self._filter_category == name))
            chip.pack(side=tk.LEFT, padx=3, pady=2)

    def _rebuild_cards(self):
        self._scroll.clear()
        self._thumbs = []
        self._cards = {}
        entries = self._current_entries()

        self._count_badge.configure(text=f"{len(entries)} 张")
        if not entries:
            empty = tk.Frame(self._scroll.inner, bg=COLORS["bg"], pady=60)
            empty.pack(fill=tk.BOTH, expand=True)
            tk.Label(empty, text="🖼", bg=COLORS["bg"], fg=COLORS["text_mute"],
                     font=font(28)).pack()
            tk.Label(empty, text="暂无历史截图" if not self._query else "没有匹配的记录",
                     bg=COLORS["bg"], fg=COLORS["text_dim"], font=font(11)).pack(pady=(8, 4))
            tk.Label(empty, text="按快捷键截图后会自动保存在这里（可在设置中关闭）",
                     bg=COLORS["bg"], fg=COLORS["text_mute"], font=font(9)).pack()
            self._status.configure(text=f"存储目录：{self.history.base_dir}")
            self._more_btn.pack_forget()
            self._update_selection_label()
            return

        columns = int(self.settings.get("history_columns") or 0)
        if columns <= 0:
            try:
                width = max(600, self._scroll.canvas.winfo_width())
            except Exception:
                width = 1000
            columns = max(1, width // (CARD_WIDTH + 14))
        columns = max(1, min(6, columns))

        grid = tk.Frame(self._scroll.inner, bg=COLORS["bg"])
        grid.pack(fill=tk.BOTH, expand=True)
        for col in range(columns):
            grid.grid_columnconfigure(col, weight=1, uniform="card")

        shown = entries[:self._limit]
        for index, entry in enumerate(shown):
            row, col = divmod(index, columns)
            card = self._make_card(grid, entry)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        remaining = len(entries) - len(shown)
        if remaining > 0:
            self._more_btn.pack(side=tk.RIGHT)
            self._more_btn.configure(text=f"加载更多（还有 {remaining} 张）")
        else:
            self._more_btn.pack_forget()

        stats = self.history.stats()
        self._status.configure(
            text=f"共 {stats['count']} 张 · 占用 {_fmt_size(stats['bytes'])} · "
                 f"收藏 {stats['pinned']} 张 · 存储目录：{stats['base_dir']}"
        )
        self._update_selection_label()

    def _load_more(self):
        self._limit += PAGE_SIZE
        self._rebuild_cards()

    def _set_filter(self, name: str):
        self._filter_category = name
        self._limit = PAGE_SIZE
        self._selected.clear()
        self.refresh()

    def _apply_search(self):
        self._query = self._search_var.get().strip()
        self._limit = PAGE_SIZE
        self._rebuild_cards()

    def _clear_search(self):
        self._search_var.set("")
        self._query = ""
        self._rebuild_cards()

    def _on_sort(self):
        self._limit = PAGE_SIZE
        self._rebuild_cards()

    # ════════════════════════════════
    # 卡片
    # ════════════════════════════════

    def _make_card(self, parent, entry: dict) -> CardContainer:
        card = CardContainer(parent, padding=8)
        card.configure(width=CARD_WIDTH)
        body = card.body

        # 缩略图
        thumb_holder = tk.Frame(body, bg=COLORS["input"], height=THUMB_BOX[1],
                                width=THUMB_BOX[0])
        thumb_holder.pack(fill=tk.X)
        thumb_holder.pack_propagate(False)

        photo = self._thumb_photo(entry)
        if photo is not None:
            tk.Label(thumb_holder, image=photo, bg=COLORS["input"]).pack(expand=True)
            self._thumbs.append(photo)
        else:
            tk.Label(thumb_holder, text="图片已丢失", bg=COLORS["input"],
                     fg=COLORS["danger"], font=font(9)).pack(expand=True)

        # 标题
        title_row = tk.Frame(body, bg=COLORS["card"])
        title_row.pack(fill=tk.X, pady=(8, 2))
        if entry.get("pinned"):
            tk.Label(title_row, text="★", bg=COLORS["card"], fg=COLORS["warn"],
                     font=font(9, True)).pack(side=tk.LEFT, padx=(0, 3))
        tk.Label(title_row, text=_short(entry.get("title"), 18), bg=COLORS["card"],
                 fg=COLORS["text"], font=font(10, True), anchor="w").pack(side=tk.LEFT)

        # 分类 + 时间
        meta = tk.Frame(body, bg=COLORS["card"])
        meta.pack(fill=tk.X)
        Chip(meta, entry.get("category") or "默认", bg=COLORS["card"]).pack(side=tk.LEFT)
        tk.Label(meta, text=_fmt_time(entry.get("created_at")), bg=COLORS["card"],
                 fg=COLORS["text_mute"], font=font(8)).pack(side=tk.RIGHT)

        # 尺寸 / 大小
        info = f"{entry.get('width', 0)}×{entry.get('height', 0)} · {_fmt_size(entry.get('size_bytes'))}"
        if entry.get("ocr_text"):
            info += " · 含文字"
        tk.Label(body, text=info, bg=COLORS["card"], fg=COLORS["text_dim"],
                 font=font(8), anchor="w").pack(fill=tk.X, pady=(3, 6))

        # 操作按钮
        actions = tk.Frame(body, bg=COLORS["card"])
        actions.pack(fill=tk.X)
        eid = entry.get("id")
        buttons = [
            ("粘贴", lambda: self._paste(entry), "CardGhost.TButton"),
            ("画笔", lambda: self._paint(entry), "CardGhost.TButton"),
            ("命名", lambda: self._rename(entry), "CardGhost.TButton"),
            ("分类", lambda: self._change_category(entry), "CardGhost.TButton"),
            ("★" if entry.get("pinned") else "☆", lambda: self._toggle_pin(entry), "CardGhost.TButton"),
            ("删", lambda: self._delete(entry), "CardGhost.TButton"),
        ]
        for text, command, style in buttons:
            ttk.Button(actions, text=text, style=style, width=4,
                       command=command).pack(side=tk.LEFT, padx=1)

        card.set_selected(eid in self._selected)
        bind_tree(card, lambda e, i=eid: self._toggle_select(i),
                  lambda e, en=entry: self._open_preview(en))
        # 右键菜单
        self._bind_context_menu(card, entry)
        self._cards[eid] = card
        return card

    def _thumb_photo(self, entry: dict):
        img = self.history.thumbnail_of(entry)
        if img is None:
            return None
        try:
            copy_img = img.copy()
            copy_img.thumbnail(THUMB_BOX, Image.LANCZOS)
            return ImageTk.PhotoImage(copy_img)
        except Exception:
            return None

    def _bind_context_menu(self, widget, entry: dict):
        menu = tk.Menu(widget, tearoff=0, bg=COLORS["panel"], fg=COLORS["text"],
                       activebackground=COLORS["card_active"], activeforeground=COLORS["accent"],
                       bd=0, font=font(9))
        menu.add_command(label="打开预览", command=lambda: self._open_preview(entry))
        menu.add_command(label="复制到剪贴板", command=lambda: self._paste(entry))
        menu.add_command(label="粘贴（自动 Ctrl+V）", command=lambda: self._paste(entry, auto=True))
        menu.add_separator()
        menu.add_command(label="画笔批注", command=lambda: self._paint(entry))
        menu.add_command(label="重命名…", command=lambda: self._rename(entry))
        menu.add_command(label="设置分类…", command=lambda: self._change_category(entry))
        menu.add_command(label="编辑标签…", command=lambda: self._edit_tags(entry))
        menu.add_command(label="收藏/取消收藏", command=lambda: self._toggle_pin(entry))
        menu.add_separator()
        menu.add_command(label="导出为 PNG…", command=lambda: self._export_one(entry))
        menu.add_command(label="在资源管理器中显示", command=lambda: self._reveal(entry))
        menu.add_separator()
        menu.add_command(label="删除记录", command=lambda: self._delete(entry))

        def popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass

        _bind_menu_recursive(widget, popup)
    # ════════════════════════════════
    # 选择
    # ════════════════════════════════

    def _toggle_select(self, entry_id: str):
        if entry_id in self._selected:
            self._selected.discard(entry_id)
        else:
            self._selected.add(entry_id)
        card = self._cards.get(entry_id)
        if card:
            card.set_selected(entry_id in self._selected)
        self._update_selection_label()

    def _select_all(self):
        for entry in self._current_entries()[:self._limit]:
            self._selected.add(entry.get("id"))
        for eid, card in self._cards.items():
            card.set_selected(True)
        self._update_selection_label()

    def _clear_selection(self):
        self._selected.clear()
        for card in self._cards.values():
            card.set_selected(False)
        self._update_selection_label()

    def _update_selection_label(self):
        count = len(self._selected)
        try:
            self._sel_label.configure(
                text=f"已选择 {count} 项" if count else "未选择（点击卡片可多选，双击查看大图）")
        except Exception:
            pass

    # ════════════════════════════════
    # 单项操作
    # ════════════════════════════════

    def _paste(self, entry: dict, auto: bool = False):
        handler = self.cb.get("paste")
        if handler:
            try:
                handler(entry, auto)
                return
            except Exception:
                pass
        from clipboard_helper import copy_image
        img = self.history.image_of(entry)
        if img is not None and copy_image(img):
            toast(self.win, "已复制历史截图", entry.get("title", ""), kind="success")
        else:
            toast(self.win, "复制失败", "图片文件可能已丢失", kind="error")

    def _paint(self, entry: dict):
        handler = self.cb.get("paint")
        if handler:
            try:
                handler(entry)
                return
            except Exception:
                pass
        img = self.history.image_of(entry)
        if img is None:
            toast(self.win, "无法打开", "图片文件已丢失", kind="error")
            return
        from paint_window import PaintWindow
        PaintWindow(self.root, img, self.settings, title=f"批注 - {entry.get('title', '')}",
                    entry=entry, history=self.history,
                    on_saved=lambda *a: self.refresh())

    def _rename(self, entry: dict):
        values = ui_theme.prompt_fields(
            self.win, "重命名截图",
            [{"key": "title", "label": "标题", "value": entry.get("title"), "required": True}],
            accent=self.settings.get("accent"))
        if not values:
            return
        self.history.rename(entry.get("id"), values["title"])
        toast(self.win, "已重命名", values["title"], kind="success")
        self._notify_changed()
        self.refresh()

    def _change_category(self, entry: dict):
        cats = self.settings.category_list()
        values = ui_theme.prompt_fields(
            self.win, "设置分类",
            [
                {"key": "category", "label": "选择已有分类", "type": "combo",
                 "value": entry.get("category"), "options": cats, "state": "readonly"},
                {"key": "new_category", "label": "或输入新分类（留空则使用上面的选择）", "value": ""},
            ],
            accent=self.settings.get("accent"))
        if not values:
            return
        category = (values.get("new_category") or "").strip() or values.get("category") or "默认"
        self.settings.add_category(category)
        self.history.set_category(entry.get("id"), category)
        toast(self.win, "已归类", category, kind="success")
        self._notify_changed()
        self.refresh()

    def _edit_tags(self, entry: dict):
        current = "，".join(entry.get("tags") or [])
        values = ui_theme.prompt_fields(
            self.win, "编辑标签",
            [{"key": "tags", "label": "标签（用逗号 / 空格分隔）", "value": current}],
            accent=self.settings.get("accent"))
        if not values:
            return
        raw = str(values.get("tags") or "").replace("，", ",").replace(" ", ",")
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        self.history.set_tags(entry.get("id"), tags)
        toast(self.win, "标签已更新", "、".join(tags) if tags else "（已清空）", kind="success")
        self.refresh()

    def _toggle_pin(self, entry: dict):
        self.history.toggle_pinned(entry.get("id"))
        self.refresh()

    def _delete(self, entry: dict):
        if self.settings.get("confirm_delete", True):
            if not ui_theme.confirm(self.win, "删除记录",
                                    f"确定要删除「{entry.get('title')}」吗？\n图片文件会一并从本地删除。",
                                    yes="删除", danger=True):
                return
        if self.history.delete(entry.get("id")):
            self._selected.discard(entry.get("id"))
            toast(self.win, "已删除记录", entry.get("title", ""), kind="success")
            self._notify_changed()
            self.refresh()

    def _delete_selected(self):
        if not self._selected:
            toast(self.win, "请先选择要删除的记录", kind="warn")
            return
        count = len(self._selected)
        if self.settings.get("confirm_delete", True):
            if not ui_theme.confirm(self.win, "批量删除",
                                    f"确定要删除选中的 {count} 条记录吗？\n"
                                    f"对应的图片文件会一并从本地删除，且无法恢复。",
                                    yes="删除", danger=True):
                return
        removed = self.history.delete_many(list(self._selected))
        self._selected.clear()
        toast(self.win, f"已删除 {removed} 条记录", kind="success")
        self._notify_changed()
        self.refresh()

    def _clear_all(self):
        total = self.history.count()
        if total == 0:
            toast(self.win, "历史记录已经是空的", kind="warn")
            return
        if not ui_theme.confirm(self.win, "清空全部历史",
                                f"确定要删除全部 {total} 条历史截图吗？\n"
                                f"所有本地图片文件都会被删除，操作不可恢复。",
                                yes="全部删除", danger=True):
            return
        removed = self.history.clear_all()
        self._selected.clear()
        toast(self.win, f"已清空 {removed} 条历史记录", kind="success")
        self._notify_changed()
        self.refresh()

    # ════════════════════════════════
    # 导入 / 导出 / 目录
    # ════════════════════════════════

    def _import_files(self):
        paths = filedialog.askopenfilenames(
            parent=self.win, title="导入图片到历史记录",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("所有文件", "*.*")])
        if not paths:
            return
        category = self._filter_category if self._filter_category not in ("全部", "★ 收藏") else "默认"
        added = 0
        for path in paths:
            if self.history.import_image(path, category=category):
                added += 1
        toast(self.win, f"已导入 {added} 张图片", f"归入分类：{category}", kind="success")
        self._notify_changed()
        self.refresh()

    def _export_one(self, entry: dict):
        default_name = f"{entry.get('title') or 'screenshot'}.png"
        path = filedialog.asksaveasfilename(
            parent=self.win, title="导出为 PNG", defaultextension=".png",
            initialfile=default_name, filetypes=[("PNG 图片", "*.png")])
        if not path:
            return
        img = self.history.image_of(entry)
        if img is None:
            toast(self.win, "导出失败", "图片文件已丢失", kind="error")
            return
        try:
            img.save(path, format="PNG")
            toast(self.win, "已导出", os.path.basename(path), kind="success")
        except Exception as e:
            toast(self.win, "导出失败", str(e), kind="error")

    def _export_selected(self):
        targets = list(self._selected)
        if not targets:
            toast(self.win, "请先选择要导出的记录", kind="warn")
            return
        dest = filedialog.askdirectory(parent=self.win, title="选择导出目录")
        if not dest:
            return
        count = self.history.export_entries(targets, dest)
        toast(self.win, f"已导出 {count} 张图片", dest, kind="success")

    def _reveal(self, entry: dict):
        try:
            path = self.history._abs(entry.get("file", ""))
            if os.path.exists(path):
                os.startfile(os.path.dirname(path))
        except Exception:
            pass

    def _open_storage_dir(self):
        try:
            os.startfile(self.history.base_dir)
        except Exception:
            toast(self.win, "无法打开目录", self.history.base_dir, kind="error")

    def _manage_categories(self):
        CategoryManagerDialog(self.win, self.settings, self.history,
                              on_done=lambda: (self._notify_changed(), self.refresh()))

    # ════════════════════════════════
    # 预览
    # ════════════════════════════════

    def _open_preview(self, entry: dict):
        entries = self._current_entries()
        try:
            index = [e.get("id") for e in entries].index(entry.get("id"))
        except ValueError:
            index = 0
        self._preview = PreviewWindow(self.root, self.settings, self.history,
                                      entries, index, callbacks=self.cb)
        self._preview.show()

    # ════════════════════════════════
    # 辅助
    # ════════════════════════════════

    def _call(self, name: str):
        handler = self.cb.get(name)
        if handler:
            try:
                handler()
            except Exception:
                pass
        else:
            toast(self.win, "该窗口未接入此功能", name, kind="warn")

    def _notify_changed(self):
        handler = self.cb.get("on_changed")
        if handler:
            try:
                handler()
            except Exception:
                pass


def stats_pinned(history) -> int:
    """收藏数量"""
    try:
        return history.stats().get("pinned", 0)
    except Exception:
        return 0


def _bind_menu_recursive(widget, popup):
    """递归绑定右键菜单"""
    try:
        widget.bind("<Button-3>", popup, add="+")
    except Exception:
        pass
    for child in widget.winfo_children():
        _bind_menu_recursive(child, popup)


# ════════════════════════════════════════════
# 分类管理
# ════════════════════════════════════════════

class CategoryManagerDialog:
    """分类管理：新增 / 重命名 / 删除 / 迁移"""

    def __init__(self, parent, settings, history, on_done=None):
        self.parent = parent
        self.settings = settings
        self.history = history
        self.on_done = on_done

        self.win = tk.Toplevel(parent)
        self.win.title("管理分类")
        self.win.configure(bg=COLORS["bg"])
        self.win.geometry("460x460")
        self.win.transient(parent)
        try:
            ui_theme.apply(self.win, settings.get("accent"))
        except Exception:
            pass

        head = tk.Frame(self.win, bg=COLORS["panel"], padx=14, pady=10)
        head.pack(fill=tk.X)
        tk.Label(head, text="管理分类", bg=COLORS["panel"], fg=COLORS["text"],
                 font=font(11, True)).pack(side=tk.LEFT)
        tk.Frame(head, bg=COLORS["accent"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(self.win, bg=COLORS["bg"], padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        self._list_holder = tk.Frame(body, bg=COLORS["bg"])
        self._list_holder.pack(fill=tk.BOTH, expand=True)

        add_row = tk.Frame(body, bg=COLORS["bg"])
        add_row.pack(fill=tk.X, pady=(10, 0))
        self._new_var = tk.StringVar()
        entry = ttk.Entry(add_row, textvariable=self._new_var, width=22)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda e: self._add())
        ttk.Button(add_row, text="新增分类", style="Accent.TButton",
                   command=self._add).pack(side=tk.LEFT, padx=6)

        ttk.Button(body, text="完成", style="Ghost.TButton",
                   command=self._close).pack(side=tk.RIGHT, pady=(12, 0))

        self.refresh()
        ui_theme.center_window(self.win, 460, 460, parent)
        try:
            self.win.grab_set()
            self.win.focus_force()
        except Exception:
            pass

    def refresh(self):
        for child in self._list_holder.winfo_children():
            child.destroy()
        stats = self.history.categories_in_use()
        for name in self.settings.category_list():
            row = tk.Frame(self._list_holder, bg=COLORS["card"], padx=10, pady=7)
            row.pack(fill=tk.X, pady=3)
            tk.Frame(row, bg=ui_theme.category_color(name), width=8, height=8).pack(side=tk.LEFT,
                                                                                   padx=(0, 8))
            tk.Label(row, text=name, bg=COLORS["card"], fg=COLORS["text"],
                     font=font(10)).pack(side=tk.LEFT)
            tk.Label(row, text=f"{stats.get(name, 0)} 张", bg=COLORS["card"],
                     fg=COLORS["text_mute"], font=font(8)).pack(side=tk.LEFT, padx=8)
            ttk.Button(row, text="重命名", style="CardGhost.TButton",
                       command=lambda n=name: self._rename(n)).pack(side=tk.RIGHT, padx=2)
            ttk.Button(row, text="删除", style="CardGhost.TButton",
                       command=lambda n=name: self._delete(n)).pack(side=tk.RIGHT, padx=2)

    def _add(self):
        name = (self._new_var.get() or "").strip()
        if not name:
            return
        self.settings.add_category(name)
        self._new_var.set("")
        self.refresh()
        self._done()

    def _rename(self, old: str):
        values = ui_theme.prompt_fields(
            self.win, "重命名分类",
            [
                {"key": "name", "label": "新分类名", "value": old, "required": True},
                {"key": "move", "label": "同时把该分类下的记录迁移过去（填写 yes 表示迁移）",
                 "value": "yes"},
            ],
            accent=self.settings.get("accent"))
        if not values:
            return
        new = values["name"].strip()
        if not new or new == old:
            return
        self.settings.rename_category(old, new)
        if str(values.get("move", "")).strip().lower() in ("yes", "y", "是", "1", "true"):
            self.history.move_category(old, new)
        self.refresh()
        self._done()

    def _delete(self, name: str):
        if len(self.settings.category_list()) <= 1:
            toast(self.win, "至少保留一个分类", kind="warn")
            return
        fallback = [c for c in self.settings.category_list() if c != name][0]
        if not ui_theme.confirm(self.win, "删除分类",
                                f"确定删除分类「{name}」吗？\n"
                                f"该分类下的记录会被移动到「{fallback}」。",
                                yes="删除", danger=True):
            return
        self.history.move_category(name, fallback)
        self.settings.remove_category(name)
        self.refresh()
        self._done()

    def _done(self):
        if self.on_done:
            try:
                self.on_done()
            except Exception:
                pass

    def _close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


# ════════════════════════════════════════════
# 预览窗口
# ════════════════════════════════════════════

class PreviewWindow:
    """单张历史截图的详情预览（支持上/下一张）"""

    def __init__(self, root, settings, history, entries: list, index: int,
                 callbacks: dict = None):
        self.root = root
        self.settings = settings
        self.history = history
        self.entries = entries or []
        self.index = max(0, min(index, len(self.entries) - 1)) if self.entries else 0
        self.cb = callbacks or {}

        self.win = None
        self._photo = None

    # ── 属性 ──

    @property
    def entry(self) -> dict:
        if not self.entries:
            return None
        return self.entries[self.index]

    def show(self):
        if self.win and self.win.winfo_exists():
            self.win.lift()
            self._reload()
            return
        self.win = tk.Toplevel(self.root)
        self.win.title("ScreenTool - 历史截图详情")
        self.win.geometry("980x680")
        self.win.minsize(720, 520)
        self.win.configure(bg=COLORS["bg"])
        try:
            ui_theme.apply(self.win, self.settings.get("accent"))
        except Exception:
            pass

        self._build_ui()
        self._reload()
        ui_theme.center_window(self.win)
        self.win.bind("<Escape>", lambda e: self._close())
        self.win.bind("<Left>", lambda e: self._nav(-1))
        self.win.bind("<Right>", lambda e: self._nav(1))
        try:
            self.win.focus_force()
        except Exception:
            pass

    def _build_ui(self):
        head = tk.Frame(self.win, bg=COLORS["panel"], padx=12, pady=9)
        head.pack(fill=tk.X)
        self._title_lbl = tk.Label(head, text="", bg=COLORS["panel"], fg=COLORS["text"],
                                   font=font(12, True))
        self._title_lbl.pack(side=tk.LEFT)
        self._pos_lbl = tk.Label(head, text="", bg=COLORS["panel"], fg=COLORS["text_mute"],
                                 font=font(9))
        self._pos_lbl.pack(side=tk.LEFT, padx=10)
        ttk.Button(head, text="上一张", style="Ghost.TButton",
                   command=lambda: self._nav(-1)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(head, text="下一张", style="Ghost.TButton",
                   command=lambda: self._nav(1)).pack(side=tk.RIGHT, padx=2)

        content = tk.Frame(self.win, bg=COLORS["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # 左：图片
        left = tk.Frame(content, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._img_holder = tk.Frame(left, bg=COLORS["input"])
        self._img_holder.pack(fill=tk.BOTH, expand=True)
        self._img_label = tk.Label(self._img_holder, bg=COLORS["input"],
                                   text="加载中…", fg=COLORS["text_mute"], font=font(10))
        self._img_label.pack(expand=True)

        self._meta_lbl = tk.Label(left, text="", bg=COLORS["bg"], fg=COLORS["text_dim"],
                                  font=font(8), anchor="w", justify="left")
        self._meta_lbl.pack(fill=tk.X, pady=(6, 0))

        # 右：信息与操作
        right = tk.Frame(content, bg=COLORS["panel"], padx=12, pady=12, width=300)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        right.pack_propagate(False)

        tk.Label(right, text="标题", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        self._title_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._title_var).pack(fill=tk.X, pady=(4, 10))

        tk.Label(right, text="分类", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        self._category_var = tk.StringVar()
        self._category_box = ttk.Combobox(right, textvariable=self._category_var,
                                          values=self.settings.category_list(),
                                          state="readonly")
        self._category_box.pack(fill=tk.X, pady=(4, 10))

        tk.Label(right, text="标签（逗号分隔）", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        self._tags_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._tags_var).pack(fill=tk.X, pady=(4, 10))

        tk.Label(right, text="备注", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        self._note = tk.Text(right, height=4, bg=COLORS["input"], fg=COLORS["text"],
                             relief=tk.FLAT, font=font(9), padx=6, pady=4,
                             highlightthickness=1, highlightbackground=COLORS["border"],
                             insertbackground=COLORS["accent"], wrap=tk.WORD)
        self._note.pack(fill=tk.X, pady=(4, 10))

        tk.Label(right, text="识别到的文字（OCR）", bg=COLORS["panel"], fg=COLORS["text_dim"],
                 font=font(9), anchor="w").pack(fill=tk.X)
        self._ocr = tk.Text(right, height=7, bg=COLORS["input"], fg=COLORS["text"],
                            relief=tk.FLAT, font=font(9), padx=6, pady=4,
                            highlightthickness=1, highlightbackground=COLORS["border"],
                            insertbackground=COLORS["accent"], wrap=tk.WORD)
        self._ocr.pack(fill=tk.BOTH, expand=True, pady=(4, 10))

        btns = tk.Frame(right, bg=COLORS["panel"])
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="保存修改", style="Accent.TButton",
                   command=self._save_fields).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="粘贴（复制到剪贴板）", style="TButton",
                   command=lambda: self._paste(auto=False)).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="粘贴并自动 Ctrl+V", style="TButton",
                   command=lambda: self._paste(auto=True)).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="画笔批注", style="TButton",
                   command=self._paint).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="复制 OCR 文字", style="TButton",
                   command=self._copy_ocr).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="删除此记录", style="Danger.TButton",
                   command=self._delete).pack(fill=tk.X, pady=2)
        ttk.Button(btns, text="关闭", style="Ghost.TButton",
                   command=self._close).pack(fill=tk.X, pady=(8, 0))

    # ── 刷新 ──

    def _reload(self):
        entry = self.entry
        if not entry:
            self._close()
            return

        self.win.title(f"ScreenTool - {entry.get('title', '')}")
        self._title_lbl.configure(text=_short(entry.get("title"), 40))
        self._pos_lbl.configure(text=f"第 {self.index + 1} / {len(self.entries)} 张")

        self._title_var.set(entry.get("title", ""))
        self._category_var.set(entry.get("category") or "默认")
        try:
            self._category_box.configure(values=self.settings.category_list())
        except Exception:
            pass
        self._tags_var.set("、".join(entry.get("tags") or []))
        _set_text(self._note, entry.get("note", ""))
        _set_text(self._ocr, entry.get("ocr_text", "") or "（未识别到文字，或识别已关闭）")

        meta = (f"{entry.get('width', 0)} × {entry.get('height', 0)} px　·　"
                f"{_fmt_size(entry.get('size_bytes'))}　·　"
                f"创建于 {_fmt_time(entry.get('created_at'))}　·　"
                f"来源 {entry.get('source', 'capture')}")
        if entry.get("colors"):
            meta += "\n主色：" + "  ".join(str(c) for c in entry["colors"][:8])
        self._meta_lbl.configure(text=meta)

        img = self.history.image_of(entry)
        if img is None:
            try:
                self._img_label.configure(image="", text="图片文件已丢失")
            except Exception:
                pass
            return
        try:
            holder_w = max(320, self._img_holder.winfo_width())
            holder_h = max(240, self._img_holder.winfo_height())
        except Exception:
            holder_w, holder_h = 620, 460
        disp = img.copy()
        disp.thumbnail((holder_w, holder_h), Image.LANCZOS)
        try:
            self._photo = ImageTk.PhotoImage(disp)
            self._img_label.configure(image=self._photo, text="")
        except Exception:
            pass

    def _nav(self, delta: int):
        if not self.entries:
            return
        self.index = (self.index + delta) % len(self.entries)
        self._reload()

    def _save_fields(self):
        entry = self.entry
        if not entry:
            return
        title = (self._title_var.get() or "").strip()
        category = (self._category_var.get() or "").strip()
        raw_tags = (self._tags_var.get() or "").replace("，", ",").replace("、", ",")
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        note = self._note.get("1.0", tk.END).strip()

        self.settings.add_category(category)
        self.history.update(entry.get("id"), title=title or "未命名截图",
                            category=category or "默认", tags=tags, note=note)
        updated = self.history.get(entry.get("id"))
        if updated:
            self.entries[self.index] = updated
        toast(self.win, "已保存修改", title or "", kind="success")
        self._notify_changed()
        self._reload()

    def _paste(self, auto: bool):
        entry = self.entry
        if not entry:
            return
        handler = self.cb.get("paste")
        if handler:
            try:
                handler(entry, auto)
                return
            except Exception:
                pass
        from clipboard_helper import copy_image
        img = self.history.image_of(entry)
        if img is not None and copy_image(img):
            toast(self.win, "已复制到剪贴板", "现在可以 Ctrl+V 粘贴", kind="success")

    def _paint(self):
        entry = self.entry
        if not entry:
            return
        handler = self.cb.get("paint")
        if handler:
            try:
                handler(entry)
                return
            except Exception:
                pass
        from paint_window import PaintWindow
        img = self.history.image_of(entry)
        if img is None:
            toast(self.win, "无法打开", "图片文件已丢失", kind="error")
            return
        PaintWindow(self.root, img, self.settings, title=f"批注 - {entry.get('title', '')}",
                    entry=entry, history=self.history,
                    on_saved=lambda *a: (self._notify_changed(), self._reload()))

    def _copy_ocr(self):
        entry = self.entry
        if not entry:
            return
        text = (entry.get("ocr_text") or "").strip()
        if not text:
            toast(self.win, "没有可复制的文字", kind="warn")
            return
        from clipboard_helper import copy_text
        if copy_text(text):
            toast(self.win, "已复制 OCR 文字", _short(text, 30), kind="success")

    def _delete(self):
        entry = self.entry
        if not entry:
            return
        if self.settings.get("confirm_delete", True):
            if not ui_theme.confirm(self.win, "删除记录",
                                    f"确定删除「{entry.get('title')}」吗？", yes="删除", danger=True):
                return
        self.history.delete(entry.get("id"))
        self.entries.pop(self.index)
        if not self.entries:
            toast(self.root, "已删除，历史记录为空", kind="success")
            self._notify_changed()
            self._close()
            return
        self.index = min(self.index, len(self.entries) - 1)
        toast(self.win, "已删除记录", kind="success")
        self._notify_changed()
        self._reload()

    def _notify_changed(self):
        handler = self.cb.get("on_changed")
        if handler:
            try:
                handler()
            except Exception:
                pass

    def _close(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.win = None


def _set_text(widget: tk.Text, value: str):
    try:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value or "")
    except Exception:
        pass
