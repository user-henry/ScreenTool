r"""
屏幕顶部的「绳子」——截图后自动挂上去的照片墙

交互设计：
- 每次截图，相片卡会从屏幕上方「落下」并挂在绳子上，带着轻微摆动
- 卡片可左右拖动排序；拖出绳子并松手 → 直接把图片粘贴到当前窗口
- 鼠标移出后绳子自动收起，只留一条发光细线；靠近即重新展开
- 右键卡片：粘贴 / 复制 / 画笔批注 / 打开历史 / 取下 / 删除

实现要点：
- 窗口无边框、置顶、不抢焦点（WS_EX_NOACTIVATE），并提供原生毛玻璃背景
- 拖拽使用 SetCapture 全局捕获鼠标，因此指针移出窗口仍能收到事件
- 所有卡片都是预渲染的 PIL 贴图（含摆动角度缓存），动画时只更新坐标
"""

import time
import tkinter as tk

from PIL import Image, ImageTk

import glass
import ui_theme
import windows_fx
from ui_theme import COLORS, font

# 摆动角度档位（度）：预渲染这些角度，动画时取最近的档位
ANGLE_STEPS = (-6.0, -3.0, 0.0, 3.0, 6.0)


class RopeWindow:
    """挂在屏幕顶部的相片绳"""

    def __init__(self, root: tk.Misc, settings, history, callbacks: dict = None):
        self.root = root
        self.settings = settings
        self.history = history
        self.callbacks = callbacks or {}

        self.win = None
        self.canvas = None

        self.cards = []            # [{entry, x, y, angle, vel, items, ...}]
        self._photos = {}          # (entry_id, angle) -> PhotoImage
        self._drag = None
        self._ghost = None
        self._ghost_label = None
        self._ghost_photo = None

        self._visible = False
        self._collapse = 0.0       # 0 = 展开，1 = 完全收起
        self._collapse_target = 0.0
        self._last_active = time.time()
        self._interacting = False
        self._hover_card = None
        self._tick_job = None

        self._sw, self._sh = 1280, 720
        self._strip_h = 200
        self._nub_h = 7            # 收起后露出的发光细线高度
        self._nub_item = None
        self._rope_item = None
        self._rope_glow_items = []
        self._chip_items = []
        self._card_w = 148
        self._card_h = 150

    # ════════════════════════════════
    # 设置读取
    # ════════════════════════════════

    def _cfg(self, key, default=None):
        try:
            value = self.settings.get(key, default)
        except Exception:
            value = default
        return default if value is None else value

    def enabled(self) -> bool:
        return bool(self._cfg("rope_enabled", True))

    def _position(self) -> str:
        return str(self._cfg("rope_position", "top") or "top").lower()

    # ════════════════════════════════
    # 生命周期
    # ════════════════════════════════

    def show(self, collapsed: bool = False):
        """显示绳子（可指定初始为收起状态）"""
        if not self.enabled():
            self.hide()
            return
        if self.win is None or not self.win.winfo_exists():
            self._build()
        self._visible = True
        self._last_active = time.time()
        self._collapse = 1.0 if collapsed else 0.0
        self._collapse_target = 1.0 if collapsed else 0.0
        self._apply_geometry()
        self._layout()
        self._redraw()
        self._ensure_tick()

    def hide(self):
        """彻底隐藏（设置里关闭绳子时）"""
        self._visible = False
        if self.win is not None:
            try:
                self.win.withdraw()
            except Exception:
                pass
        self._stop_tick()

    def toggle(self):
        """托盘菜单：展开 / 收起"""
        if self._visible and not self._is_collapsed():
            self._collapse_now()
        else:
            self._collapse = 0.85
            self._collapse_target = 0.0
            self.show(collapsed=False)
        return self._visible

    def destroy(self):
        self._stop_tick()
        self._hide_ghost()
        try:
            if self._ghost is not None:
                self._ghost.destroy()
        except Exception:
            pass
        try:
            if self.win is not None:
                self.win.destroy()
        except Exception:
            pass
        self.win = None
        self.canvas = None
        self._ghost = None

    # ════════════════════════════════
    # 窗口构建
    # ════════════════════════════════

    def _build(self):
        self._sw, self._sh = windows_fx.screen_geometry()[2:4]
        self._strip_h = int(self._cfg("rope_height", 200) or 200)

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=COLORS["bg"])

        tint = self._cfg("glass_tint", "#0B1020")
        if self._cfg("glass_enabled", True):
            windows_fx.apply_glass(
                self.win, tint=tint,
                tint_alpha=int(self._cfg("glass_tint_alpha", 0x70) or 0x70),
                mode=self._cfg("glass_mode", "blur"),
                alpha=float(self._cfg("glass_alpha", 0.97) or 0.97),
                rounded=False, no_activate=True, tool_window=True)
        else:
            windows_fx.set_no_activate(self.win, True)
            windows_fx.set_tool_window(self.win, True)

        self.canvas = tk.Canvas(self.win, bg=tint, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

        self._apply_geometry()

    def _apply_geometry(self):
        """按设置把窗口放到屏幕顶部 / 底部"""
        if self.win is None:
            return
        try:
            self._sw, self._sh = windows_fx.screen_geometry()[2:4]
        except Exception:
            pass
        self._strip_h = int(self._cfg("rope_height", 200) or 200)

        offset = int((self._strip_h - self._nub_h) * self._collapse)
        if self._position() == "bottom":
            y = self._sh - self._strip_h + offset
        else:
            y = -offset

        try:
            self.win.geometry(f"{self._sw}x{self._strip_h}+0+{y}")
            self.win.deiconify()
            self.win.lift()
        except Exception:
            pass

    def _is_collapsed(self) -> bool:
        return self._collapse > 0.5

    # ════════════════════════════════
    # 数据
    # ════════════════════════════════

    def reload(self):
        """从历史记录重建绳子上的卡片"""
        if self._drag:
            return
        if not self.enabled():
            self.hide()
            return

        limit = max(1, int(self._cfg("rope_max_items", 8) or 8))
        try:
            entries = self.history.entries(sort="newest")[:limit]
        except Exception:
            entries = []

        previous = {c["entry"].get("id"): c for c in self.cards}
        self.cards = []
        for entry in entries:
            keep = previous.get(entry.get("id"))
            card = self._make_card(entry)
            if keep:
                card["angle"] = keep.get("angle", 0.0)
                card["vel"] = keep.get("vel", 0.0)
                card["y"] = keep.get("y", 0.0)
            self.cards.append(card)

        if not self.cards:
            if self._visible or self.win is not None:
                self.show(collapsed=True)
            return
        if not self._visible:
            self.show()
        else:
            self._layout()
            self._redraw()
        self._ensure_tick()

    def add_entry(self, entry, animate: bool = True) -> bool:
        """把新截图挂到绳子最左端"""
        if not entry or not self.enabled():
            return False
        if self.win is None or not self.win.winfo_exists():
            self._build()

        limit = max(1, int(self._cfg("rope_max_items", 8) or 8))
        for card in self.cards:
            if card["entry"].get("id") == entry.get("id"):
                self.show(collapsed=False)
                return False

        card = self._make_card(entry)
        self.cards.insert(0, card)
        del self.cards[limit:]

        if animate:
            card["y"] = -float(self._strip_h)
            card["vel"] = 2.4 if self._cfg("rope_swing", True) else 0.0
        self._collapse = min(self._collapse, 0.5)
        self._collapse_target = 0.0
        self._last_active = time.time()
        if not self._visible:
            self.show()
        else:
            self._apply_geometry()
            self._layout()
            self._redraw()
        self._ensure_tick()
        return True

    def _make_card(self, entry: dict) -> dict:
        """构造一张卡片的数据结构"""
        return {
            "entry": entry,
            "x": 0.0,
            "y": 0.0,
            "angle": 0.0,
            "vel": 0.0,
            "w": 148,
            "h": 150,
            "anchor_x": 0.0,
            "angle_key": None,
            "items": {},
        }

    def _remove_card(self, card):
        self.cards = [c for c in self.cards if c is not card]
        if not self.cards:
            self.show(collapsed=True)
            return
        self._layout()
        self._redraw()
        self._ensure_tick()

    # ════════════════════════════════
    # 布局
    # ════════════════════════════════

    def _layout(self):
        """按屏幕宽度计算卡片尺寸与锚点"""
        count = len(self.cards)
        if not count:
            return
        margin, gap = 32, 16
        avail = max(200, self._sw - margin * 2 - 130)   # 右侧留给「历史」入口
        card_w = int((avail - gap * (count - 1)) / count)
        card_w = max(92, min(168, card_w))
        card_h = max(96, min(190, int(card_w * 0.92) + 18))

        for index, card in enumerate(self.cards):
            card["w"] = card_w
            card["h"] = card_h
            card["anchor_x"] = margin + index * (card_w + gap) + card_w / 2
            if not self._drag or self._drag.get("card") is not card:
                card["x"] = card["anchor_x"] - card_w / 2
        self._card_w, self._card_h = card_w, card_h

    def _rope_y(self, x: float) -> float:
        """绳子的悬链线（抛物线近似）"""
        t = max(0.0, min(1.0, x / max(2, self._sw)))
        sag = 14 if self._position() == "top" else 10
        base = 26 if self._position() == "top" else 18
        return base + sag * (1 - (2 * t - 1) ** 2)

    # ════════════════════════════════
    # 绘制
    # ════════════════════════════════

    def _redraw(self):
        """重建全部画布元素"""
        canvas = self.canvas
        if canvas is None:
            return
        canvas.delete("all")
        self._rope_item = None
        self._nub_item = None
        self._rope_glow_items = []
        self._chip_items = []

        self._draw_rope()
        for card in self.cards:
            self._draw_card_items(card)
        self._draw_footer_chip()
        if self._collapse > 0.02:
            self._draw_nub()

    def _draw_rope(self):
        """画绳子（多层描边）+ 两端锚点"""
        canvas = self.canvas
        sag = 14 if self._position() == "top" else 10
        base = 26 if self._position() == "top" else 18

        backdrop = self._backdrop_photo(sag, base)
        if backdrop is not None:
            canvas.create_image(0, 0, anchor=tk.NW, image=backdrop)

        steps = max(32, self._sw // 8)
        points = []
        for i in range(steps + 1):
            t = i / steps
            x = t * self._sw
            y = base + sag * (1 - (2 * t - 1) ** 2)
            points.extend((x, y))

        glow = canvas.create_line(*points, fill=COLORS["accent_dim"],
                                  width=7, smooth=True, capstyle=tk.ROUND)
        canvas.itemconfigure(glow, stipple="gray25")
        self._rope_glow_items.append(glow)
        self._rope_glow_items.append(canvas.create_line(
            *points, fill="#5C6B88", width=4, smooth=True, capstyle=tk.ROUND))
        self._rope_item = canvas.create_line(
            *points, fill="#C6D2E6", width=1, smooth=True, capstyle=tk.ROUND)

        for x in (10, self._sw - 10):
            t = x / max(1, self._sw)
            y = base + sag * (1 - (2 * t - 1) ** 2)
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                               fill=COLORS["accent_dim"], outline="")
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2,
                               fill=COLORS["accent"], outline="")

    def _backdrop_photo(self, sag: int, base: int):
        """条带背景贴图（带缓存）"""
        key = (self._sw, self._strip_h, sag, base,
               self._cfg("glass_tint", "#0B1020"))
        if getattr(self, "_backdrop_key", None) == key:
            return getattr(self, "_backdrop_img", None)
        try:
            image = glass.strip_backdrop(
                self._sw, self._strip_h,
                tint=self._cfg("glass_tint", "#0B1020"),
                accent=COLORS["accent"], rope_y=base, sag=sag)
        except Exception:
            return None
        photo = ImageTk.PhotoImage(image)
        self._backdrop_key = key
        self._backdrop_img = photo
        return photo

    def _draw_card_items(self, card: dict):
        """为一张卡片创建画布元素"""
        canvas = self.canvas
        photo = self._card_photo(card)
        anchor_x = card.get("anchor_x", card["x"] + card["w"] / 2)
        rope_y = self._rope_y(anchor_x)
        clip_x = card["x"] + card["w"] / 2
        clip_y = card["y"] + rope_y + 12

        string_item = canvas.create_line(clip_x, rope_y, clip_x, clip_y,
                                         fill="#8A98B4", width=2)
        highlight = canvas.create_rectangle(
            card["x"] - 5, card["y"] + 6, card["x"] + card["w"] + 5,
            card["y"] + card["h"] + 14,
            outline=COLORS["accent"], width=2, state="hidden")
        img_item = canvas.create_image(card["x"], card["y"], anchor=tk.NW,
                                       image=photo)

        card["items"] = {
            "string": string_item,
            "highlight": highlight,
            "image": img_item,
        }

    def _card_photo(self, card: dict):
        """取（或生成）当前角度对应的卡片贴图"""
        entry = card["entry"]
        angle = self._nearest_angle(card["angle"])
        key = (entry.get("id"), angle)
        cached = self._photos.get(key)
        if cached is not None:
            card["angle_key"] = angle
            return cached

        try:
            image = self.history.thumbnail_of(entry)
        except Exception:
            image = None

        accent = COLORS["accent"]
        try:
            accent = ui_theme.category_color(entry.get("category") or "")
        except Exception:
            pass

        card_img = glass.photo_card(
            image, card["w"], card["h"],
            caption=(entry.get("title") or "")[:24],
            accent=accent, pinned=bool(entry.get("pinned")))
        if angle:
            card_img = glass.rotate_card(card_img, angle)

        photo = ImageTk.PhotoImage(card_img)
        self._photos[key] = photo
        if len(self._photos) > 180:
            for old_key in list(self._photos.keys())[:60]:
                if old_key != key:
                    self._photos.pop(old_key, None)
        card["angle_key"] = angle
        return photo

    @staticmethod
    def _nearest_angle(angle: float) -> float:
        return min(ANGLE_STEPS, key=lambda a: abs(a - angle))

    def _draw_footer_chip(self):
        """右侧的「历史」入口"""
        canvas = self.canvas
        if canvas is None or not self.cards:
            return
        try:
            count = self.history.count()
        except Exception:
            count = len(self.cards)
        y = self._rope_y(self._sw * 0.5) + 8
        item = canvas.create_text(self._sw - 18, y, text=f"历史 {count} 张 ›",
                                  anchor=tk.NE, fill=COLORS["accent"],
                                  font=font(9, True))
        box = canvas.bbox(item)
        if box:
            rect = canvas.create_rectangle(box[0] - 9, box[1] - 5,
                                           box[2] + 9, box[3] + 5,
                                           outline=COLORS["border_light"],
                                           fill=COLORS["card"], width=1)
            canvas.tag_lower(rect, item)
            self._chip_items = [rect, item]

    def _draw_nub(self):
        """收起状态：只留一条发光细线"""
        canvas = self.canvas
        if canvas is None:
            return
        y = self._strip_h - self._nub_h // 2 - 1
        self._nub_item = canvas.create_line(0, y, self._sw, y,
                                            fill=COLORS["accent"], width=2)
        for item in self._rope_glow_items:
            canvas.itemconfigure(item, state="hidden")
        if self._rope_item:
            canvas.itemconfigure(self._rope_item, state="hidden")
        for card in self.cards:
            for name in ("string", "image", "highlight"):
                item_id = card["items"].get(name)
                if item_id:
                    canvas.itemconfigure(item_id, state="hidden")

    # ════════════════════════════════
    # 动画
    # ════════════════════════════════

    def _ensure_tick(self):
        if self._tick_job is None and self._visible:
            try:
                self._tick_job = self.root.after(16, self._tick)
            except Exception:
                self._tick_job = None

    def _stop_tick(self):
        if self._tick_job is not None:
            try:
                self.root.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None

    def _busy(self) -> bool:
        if abs(self._collapse - self._collapse_target) > 0.002:
            return True
        if self._drag:
            return True
        for card in self.cards:
            if abs(card["y"]) > 0.4:
                return True
            if abs(card["angle"]) > 0.05 or abs(card["vel"]) > 0.05:
                return True
        return False

    def _tick(self):
        self._tick_job = None
        if not self._visible or self.win is None:
            return

        # 1. 收起 / 展开动画
        if abs(self._collapse - self._collapse_target) > 0.002:
            collapsed = self._collapse > 0.02
            self._collapse += (self._collapse_target - self._collapse) * 0.18
            if abs(self._collapse_target - self._collapse) < 0.01:
                self._collapse = self._collapse_target
            self._apply_geometry()
            now_collapsed = self._collapse > 0.02
            if now_collapsed != collapsed:
                self._redraw()

        # 2. 自动收起
        if (self._cfg("rope_autohide", True) and not self._interacting
                and self._collapse_target < 0.5 and self._hover_card is None):
            idle = time.time() - self._last_active
            delay = float(self._cfg("rope_autohide_delay", 6) or 6)
            if self.cards and idle > delay:
                self._collapse_target = 1.0

        # 3. 卡片：落下 + 摆动
        swing_enabled = bool(self._cfg("rope_swing", True))
        for card in self.cards:
            if not self._drag or self._drag.get("card") is not card:
                if abs(card["y"]) > 0.4:
                    card["y"] += (0.0 - card["y"]) * 0.20
                else:
                    card["y"] = 0.0
            if swing_enabled and (not self._drag or self._drag.get("card") is not card):
                card["vel"] += (-0.055 * card["angle"]) - (0.06 * card["vel"])
                card["angle"] = max(-9.0, min(9.0, card["angle"] + card["vel"]))
            elif not swing_enabled:
                card["angle"] = 0.0
                card["vel"] = 0.0

        self._update_positions()

        if self._busy():
            self._ensure_tick()
        else:
            self._stop_tick()

    def _update_positions(self):
        """把卡片当前状态写回画布"""
        canvas = self.canvas
        if canvas is None:
            return
        for card in self.cards:
            items = card.get("items") or {}
            if not items:
                continue
            anchor_x = card.get("anchor_x", card["x"] + card["w"] / 2)
            rope_y = self._rope_y(anchor_x)
            clip_x = card["x"] + card["w"] / 2
            clip_y = card["y"] + rope_y + 12
            try:
                canvas.coords(items["string"], clip_x, rope_y, clip_x, clip_y)
                canvas.coords(items["highlight"],
                              card["x"] - 5, card["y"] + 6,
                              card["x"] + card["w"] + 5,
                              card["y"] + card["h"] + 14)
                canvas.coords(items["image"], card["x"], card["y"])
                wanted = self._nearest_angle(card["angle"])
                if card.get("angle_key") != wanted:
                    canvas.itemconfigure(items["image"], image=self._card_photo(card))
                canvas.itemconfigure(
                    items["highlight"],
                    state="normal" if card is self._hover_card else "hidden")
            except Exception:
                continue

    # ════════════════════════════════
    # 命中测试与鼠标事件
    # ════════════════════════════════

    def _hit_test(self, x: float, y: float):
        """返回鼠标下的卡片"""
        for card in reversed(self.cards):
            cx, cy = card["x"], card["y"]
            if (cx <= x <= cx + card["w"] + 12 and
                    cy - 14 <= y <= cy + card["h"] + 20):
                return card
        return None

    def _hit_chip(self, x, y) -> bool:
        if not self._chip_items:
            return False
        try:
            box = self.canvas.bbox(self._chip_items[1])
            return bool(box and box[0] - 10 <= x <= box[2] + 10
                        and box[1] - 8 <= y <= box[3] + 8)
        except Exception:
            return False

    def _on_enter(self, _event=None):
        self._last_active = time.time()
        if self._collapse_target > 0.5:
            self._collapse_target = 0.0
        self._ensure_tick()

    def _on_leave(self, _event=None):
        self._hover_card = None
        self._last_active = time.time()
        self._ensure_tick()

    def _on_hover(self, event):
        self._last_active = time.time()
        if self._collapse_target > 0.5:
            self._collapse_target = 0.0
        hovered = self._hit_test(event.x, event.y)
        if hovered is not self._hover_card:
            self._hover_card = hovered
            self._update_positions()

    def _on_press(self, event):
        self._last_active = time.time()
        self._interacting = True
        card = self._hit_test(event.x, event.y)
        if card is None:
            if self._hit_chip(event.x, event.y):
                self._call("history")
            return
        self._drag = {
            "card": card,
            "start": (event.x, event.y),
            "offset": (event.x - card["x"], event.y - card["y"]),
            "moved": False,
        }
        window = self.canvas if self.canvas is not None else self.win
        windows_fx.begin_capture(window)
        self._ensure_tick()

    def _on_motion(self, event):
        drag = self._drag
        if not drag:
            return
        card = drag["card"]
        if (abs(event.x - drag["start"][0]) > 4 or
                abs(event.y - drag["start"][1]) > 4):
            drag["moved"] = True

        card["x"] = event.x - drag["offset"][0]
        card["y"] = event.y - drag["offset"][1]
        card["angle"] = max(-9.0, min(9.0, (event.x - drag["start"][0]) * 0.12))
        card["vel"] = 0.0

        outside = event.y > self._strip_h + 6 or event.y < -6
        if outside and self._cfg("rope_drag_paste", True):
            self._show_ghost(card, event.x, event.y)
        else:
            self._hide_ghost()
        self._update_positions()
        self._ensure_tick()

    def _on_release(self, event):
        windows_fx.end_capture()
        self._interacting = False
        self._hide_ghost()

        drag = self._drag
        self._drag = None
        if not drag:
            return
        card = drag["card"]

        inside = -10 <= event.y <= self._strip_h + 10
        if inside:
            if drag["moved"]:
                self._reorder(card)
            self._layout()
            card["angle"] = card["angle"] * 0.5
            card["vel"] = card["angle"] * 0.4
            self._redraw()
            self._last_active = time.time()
            self._ensure_tick()
            return

        if self._cfg("rope_drag_paste", True):
            self._drop_out(card)
        else:
            self._layout()
            self._redraw()
            self._ensure_tick()

    def _reorder(self, card):
        """按拖动后的横坐标重新插入排序"""
        others = [c for c in self.cards if c is not card]
        index = 0
        for other in others:
            if card["x"] + card["w"] / 2 > other.get("anchor_x", 0):
                index += 1
        others.insert(min(index, len(others)), card)
        self.cards = others

    def _on_right_click(self, event):
        self._last_active = time.time()
        card = self._hit_test(event.x, event.y)
        menu = self._build_menu(card) if card is not None else self._build_menu(None)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _build_menu(self, card):
        menu = tk.Menu(self.win, tearoff=0, bg=COLORS["panel"], fg=COLORS["text"],
                       activebackground=COLORS["card_active"],
                       activeforeground=COLORS["text"], bd=0)
        if card is None:
            menu.add_command(label="全部历史截图", command=lambda: self._call("history"))
            menu.add_command(label="刷新绳子", command=self.reload)
            menu.add_separator()
            menu.add_command(label="收起绳子", command=self._collapse_now)
            return menu

        entry = card["entry"]
        menu.add_command(label="粘贴到当前窗口",
                         command=lambda: self._paste(entry, True))
        menu.add_command(label="只复制到剪贴板",
                         command=lambda: self._paste(entry, False))
        menu.add_separator()
        menu.add_command(label="画笔批注", command=lambda: self._call("paint", entry))
        menu.add_command(label="在历史中查看", command=lambda: self._call("history"))
        menu.add_separator()
        menu.add_command(label="从绳子取下", command=lambda: self._remove_card(card))
        menu.add_command(label="删除这条记录",
                         command=lambda: self._call("delete", entry))
        return menu

    def _collapse_now(self):
        self._collapse_target = 1.0
        self._last_active = time.time()
        self._ensure_tick()

    def _paste(self, entry, auto: bool = True):
        self._call("paste", entry, auto)

    def _call(self, name, *args):
        callback = self.callbacks.get(name)
        if not callback:
            return None
        try:
            return callback(*args)
        except Exception:
            return None

    # ════════════════════════════════
    # 拖出到其它应用
    # ════════════════════════════════

    def _drop_out(self, card):
        """在绳子外松手：粘贴到光标下的应用窗口"""
        info = windows_fx.window_under_cursor()
        own = [self.win]
        if self._ghost is not None:
            own.append(self._ghost)
        target_ok = (not info.get("is_desktop")
                     and not windows_fx.is_own_window(info.get("root"), own))

        if not target_ok:
            self._layout()
            self._redraw()
            self._ensure_tick()
            return

        self._paste(card["entry"], True)
        if self._cfg("rope_remove_after_paste", False):
            self._remove_card(card)
        else:
            self._layout()
            self._redraw()
        self._ensure_tick()

    def _ghost_target_title(self) -> str:
        info = windows_fx.window_under_cursor()
        title = (info.get("title") or "").strip()
        if info.get("is_desktop") or not title:
            return "当前窗口"
        return title

    def _show_ghost(self, card, x, y):
        """跟随光标的半透明预览（含目标窗口提示）"""
        if self._ghost is None or not self._ghost.winfo_exists():
            self._ghost = tk.Toplevel(self.root)
            self._ghost.overrideredirect(True)
            self._ghost.attributes("-topmost", True)
            try:
                self._ghost.attributes("-alpha", 0.93)
            except Exception:
                pass
            windows_fx.set_no_activate(self._ghost, True)
            windows_fx.set_tool_window(self._ghost, True)
            self._ghost_label = tk.Label(self._ghost, bd=0, bg=COLORS["bg"])
            self._ghost_label.pack()

        try:
            image = self.history.thumbnail_of(card["entry"])
        except Exception:
            image = None

        preview = glass.photo_card(image, card["w"], card["h"],
                                   caption="松开即粘贴", accent=COLORS["accent"],
                                   shadow=8)
        hint = glass.badge(f"→ {self._ghost_target_title()[:14]}",
                           accent=COLORS["success"], font_size=10)

        canvas_img = Image.new(
            "RGBA",
            (max(preview.width, hint.width),
             preview.height + hint.height + 4),
            (0, 0, 0, 0))
        canvas_img.alpha_composite(preview, (0, 0))
        canvas_img.alpha_composite(hint, (6, preview.height + 2))

        self._ghost_photo = ImageTk.PhotoImage(canvas_img)
        self._ghost_label.configure(image=self._ghost_photo)
        try:
            self._ghost.geometry(
                f"{canvas_img.width}x{canvas_img.height}+{int(x + 20)}+{int(y + 16)}")
            self._ghost.deiconify()
            self._ghost.lift()
        except Exception:
            pass

    def _hide_ghost(self):
        if self._ghost is not None:
            try:
                self._ghost.withdraw()
            except Exception:
                pass

    # ════════════════════════════════
    # 设置变化
    # ════════════════════════════════

    def refresh_settings(self):
        """设置保存后重读几何与特效"""
        if not self.enabled():
            self.hide()
            return
        if self.win is None or not self.win.winfo_exists():
            self.show(collapsed=True)
            return
        if self._cfg("glass_enabled", True):
            windows_fx.apply_glass(
                self.win, tint=self._cfg("glass_tint", "#0B1020"),
                tint_alpha=int(self._cfg("glass_tint_alpha", 0x70) or 0x70),
                mode=self._cfg("glass_mode", "blur"),
                alpha=float(self._cfg("glass_alpha", 0.97) or 0.97),
                no_activate=True, tool_window=True)
        else:
            windows_fx.disable_blur(self.win)
            try:
                self.win.attributes("-alpha", 1.0)
            except Exception:
                pass
        self._photos.clear()
        self._apply_geometry()
        self.reload()
