"""
全屏截图叠加层（科技风）

- 全屏半透明窗口，暗化显示桌面
- 鼠标拖拽框选区域，选区内显示原图亮度，并显示十字准线与尺寸标签
- 可选跟随放大镜（显示鼠标附近的像素与颜色）
- 支持：右键 / ESC 取消 · 回车 / 双击 截取整个屏幕
- 使用 wait_window 阻塞等待用户操作
"""

import time
import tkinter as tk
from tkinter import Canvas
import ctypes

from PIL import Image, ImageGrab, ImageTk, ImageEnhance

from ui_theme import COLORS, font, mono

ACCENT = COLORS["accent"]
ACCENT_SOFT = "#7C5CFF"


def _get_virtual_screen_rect():
    """获取所有显示器的虚拟屏幕矩形"""
    user32 = ctypes.windll.user32
    left = user32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
    top = user32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN
    width = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    return left, top, width, height


class ScreenCapture:
    """全屏框选截图（暗色科技风叠加层）"""

    def __init__(self, root: tk.Tk, settings=None):
        self.root = root
        self.settings = settings
        self._result = None
        self.win = None

    # ════════════════════════════════
    # 主流程
    # ════════════════════════════════

    def capture(self):
        """
        启动截图并阻塞等待用户操作。

        Returns:
            {"image": PIL.Image, "x","y","w","h", "full_image", "full_origin"} | None
        """
        self._result = None
        self.win = None
        self.root.after(0, self._start_capture)

        deadline = time.time() + 5
        while self.win is None and time.time() < deadline:
            self.root.update()
        if self.win is None:
            return None

        # 用户可能极快完成框选（甚至在本函数进入等待前就松开鼠标），
        # 此时窗口已经销毁，直接返回结果即可，避免 wait_window 抛 TclError
        try:
            if self.win.winfo_exists():
                self.root.wait_window(self.win)
        except tk.TclError:
            pass
        return self._result

    # ════════════════════════════════
    # 窗口搭建
    # ════════════════════════════════

    def _setting(self, key, default=None):
        if self.settings is None:
            return default
        try:
            return self.settings.get(key, default)
        except Exception:
            return default

    def _start_capture(self):
        """在主线程中创建全屏截图窗口"""
        left, top, vw, vh = _get_virtual_screen_rect()

        # 截取全屏（所有显示器）
        self._full_img = ImageGrab.grab(bbox=(left, top, left + vw, top + vh), all_screens=True)
        self._origin = (left, top)

        # 暗化背景
        strength = float(self._setting("dim_strength", 0.40) or 0.40)
        strength = max(0.05, min(0.95, strength))
        self._dark_img = ImageEnhance.Brightness(self._full_img).enhance(max(0.05, 1.0 - strength))

        # 无边框全屏窗口
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{vw}x{vh}+{left}+{top}")
        self.win.config(cursor="crosshair", bg="black")
        try:
            self.win.attributes("-alpha", 1.0)
        except Exception:
            pass
        self.win.focus_force()

        self.win.bind("<Escape>", self._on_cancel)
        self.win.bind("<Button-3>", self._on_cancel)
        self.win.bind("<Return>", self._on_enter)
        self.win.bind("<KP_Enter>", self._on_enter)

        self.canvas = Canvas(self.win, width=vw, height=vh, highlightthickness=0,
                             bg="black", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 背景图
        self._dark_tk = ImageTk.PhotoImage(self._dark_img)
        self._dark_tk_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self._dark_tk)

        # 状态
        self._vw, self._vh = vw, vh
        self._start_pt = None
        self._rect_id = None
        self._bright_id = None
        self._size_ids = []
        self._guide_ids = []
        self._magnifier_ids = []
        self._magnifier_img_id = None
        self._magnifier_tk = None
        self._has_region = False

        # 交互绑定
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Motion>", self._on_motion)

        self._draw_hint()

    # ════════════════════════════════
    # 顶部提示条
    # ════════════════════════════════

    def _draw_hint(self):
        if not self._setting("capture_hint", True):
            return
        text = ("  拖拽鼠标框选区域　·　双击 / 回车 截取整屏　·　"
                "右键 / ESC 取消　·　截图后自动保存到历史  ")
        item = self.canvas.create_text(self._vw // 2, 34, text=text, fill=COLORS["text"],
                                       font=font(10, True))
        bbox = self.canvas.bbox(item)
        if not bbox:
            return
        pad_x, pad_y = 18, 10
        bg = self.canvas.create_rectangle(
            bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y,
            fill="#0B1020", outline=ACCENT, width=1)
        # 顶部装饰线
        self.canvas.create_line(0, 0, self._vw, 0, fill=ACCENT, width=2)
        self.canvas.tag_lower(bg, item)
        self._hint_ids = (bg, item)

    # ════════════════════════════════
    # 清除叠加元素
    # ════════════════════════════════

    def _clear_region(self):
        for rid in [self._rect_id, self._bright_id] + self._size_ids + self._guide_ids:
            if rid:
                try:
                    self.canvas.delete(rid)
                except Exception:
                    pass
        self._rect_id = None
        self._bright_id = None
        self._size_ids = []
        self._guide_ids = []

    def _clear_magnifier(self):
        for rid in self._magnifier_ids:
            try:
                self.canvas.delete(rid)
            except Exception:
                pass
        self._magnifier_ids = []
        self._magnifier_img_id = None

    # ════════════════════════════════
    # 鼠标交互
    # ════════════════════════════════

    def _on_press(self, event):
        self._start_pt = (event.x, event.y)

    def _on_motion(self, event):
        if self._start_pt is None:
            self._draw_crosshair(event.x, event.y)
        self._draw_magnifier(event.x, event.y)

    def _on_drag(self, event):
        if self._start_pt is None:
            return
        x1, y1 = self._start_pt
        x2, y2 = event.x, event.y
        rx, ry = min(x1, x2), min(y1, y2)
        rw, rh = abs(x2 - x1), abs(y2 - y1)

        self._clear_region()
        self._draw_crosshair(x2, y2)
        self._draw_magnifier(x2, y2)

        if rw < 4 and rh < 4:
            return

        self._has_region = True

        # 选区原图亮区
        if rw > 0 and rh > 0:
            crop = self._full_img.crop((rx, ry, rx + rw, ry + rh))
            self._bright_tk = ImageTk.PhotoImage(crop)
            self._bright_id = self.canvas.create_image(rx, ry, anchor=tk.NW,
                                                       image=self._bright_tk)
            try:
                self.canvas.tag_raise(self._bright_id, self._dark_tk_id)
            except Exception:
                pass

        # 选框（科技风双线）
        self._rect_id = self.canvas.create_rectangle(
            rx, ry, rx + rw, ry + rh, outline=ACCENT, width=2)
        # 四角
        corner = 14
        self._size_ids.append(self.canvas.create_line(rx, ry, rx + corner, ry, fill=ACCENT_SOFT, width=3))
        self._size_ids.append(self.canvas.create_line(rx, ry, rx, ry + corner, fill=ACCENT_SOFT, width=3))
        self._size_ids.append(self.canvas.create_line(rx + rw, ry + rh, rx + rw - corner, ry + rh, fill=ACCENT_SOFT, width=3))
        self._size_ids.append(self.canvas.create_line(rx + rw, ry + rh, rx + rw, ry + rh - corner, fill=ACCENT_SOFT, width=3))

        # 尺寸标签
        label = f" {rw} × {rh} "
        ly = ry - 22 if ry > 30 else ry + rh + 8
        text_id = self.canvas.create_text(rx + 4, ly, text=label, anchor=tk.NW,
                                          fill=COLORS["text"], font=mono(10, True))
        bbox = self.canvas.bbox(text_id)
        if bbox:
            bg_id = self.canvas.create_rectangle(bbox[0] - 6, bbox[1] - 3, bbox[2] + 6, bbox[3] + 3,
                                                fill="#0B1020", outline=ACCENT, width=1)
            self.canvas.tag_lower(bg_id, text_id)
            self._size_ids.extend([bg_id, text_id])
        else:
            self._size_ids.append(text_id)

    def _draw_crosshair(self, x, y):
        for rid in self._guide_ids:
            try:
                self.canvas.delete(rid)
            except Exception:
                pass
        self._guide_ids = []
        if self._start_pt is not None:
            return
        try:
            self._guide_ids.append(self.canvas.create_line(0, y, self._vw, y,
                                                           fill="#3DE1FF", dash=(3, 5)))
            self._guide_ids.append(self.canvas.create_line(x, 0, x, self._vh,
                                                           fill="#3DE1FF", dash=(3, 5)))
        except Exception:
            pass

    def _draw_magnifier(self, x, y):
        """跟随鼠标的放大镜（显示像素与颜色）"""
        self._clear_magnifier()
        if not self._setting("magnifier", True) or self._start_pt is not None:
            return

        zoom = 8
        box = 70
        half = box // 2
        try:
            region = self._full_img.crop((x - half, y - half, x + half, y + half))
        except Exception:
            return
        if region.width < 4 or region.height < 4:
            return
        big = region.resize((region.width * zoom, region.height * zoom), Image.NEAREST)

        # 位置：默认右下，靠近边缘时翻转
        ox = x + 26
        oy = y + 26
        if ox + big.width > self._vw:
            ox = x - big.width - 26
        if oy + big.height + 26 > self._vh:
            oy = y - big.height - 26
        ox = max(4, ox)
        oy = max(4, oy)

        try:
            self._magnifier_tk = ImageTk.PhotoImage(big)
        except Exception:
            return
        self._magnifier_img_id = self.canvas.create_image(ox, oy, anchor=tk.NW,
                                                          image=self._magnifier_tk)
        self._magnifier_ids.append(self._magnifier_img_id)
        self._magnifier_ids.append(self.canvas.create_rectangle(
            ox - 1, oy - 1, ox + big.width + 1, oy + big.height + 1,
            outline=ACCENT, width=1))
        self._magnifier_ids.append(self.canvas.create_rectangle(
            ox + half * zoom, oy + half * zoom, ox + (half + 1) * zoom, oy + (half + 1) * zoom,
            outline=ACCENT_SOFT, width=1))

        # 颜色与坐标信息
        try:
            px = self._full_img.getpixel((min(max(x, 0), self._full_img.width - 1),
                                          min(max(y, 0), self._full_img.height - 1)))
            if isinstance(px, tuple) and len(px) >= 3:
                hex_color = "#{:02X}{:02X}{:02X}".format(px[0], px[1], px[2])
                info = f"{x},{y}  {hex_color}"
                info_id = self.canvas.create_text(ox, oy + big.height + 6, text=info,
                                                  anchor=tk.NW, fill=COLORS["text_dim"],
                                                  font=mono(8))
                self._magnifier_ids.append(info_id)
        except Exception:
            pass

    def _on_release(self, event):
        if self._start_pt is None:
            return
        x1, y1 = self._start_pt
        x2, y2 = event.x, event.y
        rx, ry = min(x1, x2), min(y1, y2)
        rw, rh = abs(x2 - x1), abs(y2 - y1)
        self._finish(rx, ry, rw, rh)

    def _on_double(self, _event=None):
        """双击截取整个屏幕"""
        self._finish(0, 0, self._vw, self._vh)

    def _on_enter(self, _event=None):
        self._finish(0, 0, self._vw, self._vh)

    def _finish(self, rx, ry, rw, rh):
        full = self._full_img
        try:
            self.win.destroy()
        except Exception:
            pass

        if rw < 8 or rh < 8:
            self._result = None
            return

        cx1 = max(0, rx)
        cy1 = max(0, ry)
        cx2 = min(full.width, rx + rw)
        cy2 = min(full.height, ry + rh)
        if cx2 - cx1 < 8 or cy2 - cy1 < 8:
            self._result = None
            return

        left, top = self._origin
        self._result = {
            "image": full.crop((cx1, cy1, cx2, cy2)),
            "x": left + cx1,
            "y": top + cy1,
            "w": cx2 - cx1,
            "h": cy2 - cy1,
            "full_image": full,
            "full_origin": self._origin,
        }

    def _on_cancel(self, _event=None):
        try:
            self.win.destroy()
        except Exception:
            pass
        self._result = None
