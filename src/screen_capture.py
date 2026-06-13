"""
全屏截图叠加层
- 全屏半透明窗口，显示暗化截图
- 鼠标拖拽框选区域，选区内显示原图亮度
- 支持 ESC 取消
- 使用 wait_window 阻塞等待用户操作
"""
import tkinter as tk
from tkinter import Canvas
import ctypes
from PIL import Image, ImageGrab, ImageTk, ImageEnhance


def _get_virtual_screen_rect():
    """获取所有显示器的虚拟屏幕矩形"""
    user32 = ctypes.windll.user32
    left = user32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
    top = user32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN
    width = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    return left, top, width, height


class ScreenCapture:
    """全屏框选截图"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self._result = None

    def capture(self):
        """
        启动截图并阻塞等待用户操作。

        Returns:
            {"image": PIL.Image, "x": int, "y": int, "w": int, "h": int} | None
        """
        self._result = None
        self.win = None
        self.root.after(0, self._start_capture)
        # 先处理事件队列直到窗口创建完成
        while self.win is None:
            self.root.update()
        # wait_window 运行嵌套事件循环，直到 capture 窗口被销毁
        self.root.wait_window(self.win)
        return self._result

    def _start_capture(self):
        """在主线程中创建全屏截图窗口"""
        left, top, vw, vh = _get_virtual_screen_rect()

        # 截取全屏
        self._full_img = ImageGrab.grab(bbox=(left, top, left + vw, top + vh), all_screens=True)

        # 创建暗化版本（亮度降至 35%）
        enhancer = ImageEnhance.Brightness(self._full_img)
        self._dark_img = enhancer.enhance(0.35)

        # 创建无边框全屏 Toplevel
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.geometry(f"{vw}x{vh}+{left}+{top}")
        self.win.config(cursor='cross')
        self.win.focus_force()

        # ESC 取消
        self.win.bind("<Escape>", self._on_cancel)

        # Canvas 铺满窗口
        self.canvas = Canvas(self.win, width=vw, height=vh, highlightthickness=0, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 渲染暗化背景
        self._dark_tk = ImageTk.PhotoImage(self._dark_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._dark_tk)

        # 选框绘制状态
        self._start_x = None
        self._start_y = None
        self._rect_id = None
        self._bright_id = None
        self._info_id = None
        self._info_bg_id = None

        # 鼠标交互
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _clear_overlay(self):
        """清除选框和文字叠加层"""
        for rid in [self._rect_id, self._bright_id, self._info_id, self._info_bg_id]:
            if rid:
                self.canvas.delete(rid)
        self._rect_id = None
        self._bright_id = None
        self._info_id = None
        self._info_bg_id = None

    def _on_press(self, event):
        self._start_x = event.x
        self._start_y = event.y

    def _on_drag(self, event):
        if self._start_x is None:
            return

        x1, y1 = self._start_x, self._start_y
        x2, y2 = event.x, event.y
        rx = min(x1, x2)
        ry = min(y1, y2)
        rw = abs(x2 - x1)
        rh = abs(y2 - y1)

        self._clear_overlay()
        if rw < 5 and rh < 5:
            return

        # 裁剪原图亮区并显示在选框中
        crop = self._full_img.crop((rx, ry, rx + rw, ry + rh))
        if rw > 0 and rh > 0:
            crop_resized = crop.resize((rw, rh), Image.LANCZOS)
            self._bright_tk = ImageTk.PhotoImage(crop_resized)
            self._bright_id = self.canvas.create_image(rx, ry, anchor=tk.NW, image=self._bright_tk)

        # 选框边框
        self._rect_id = self.canvas.create_rectangle(
            rx, ry, rx + rw, ry + rh,
            outline='#4A90D9', width=2,
        )

        # 尺寸标签
        info_text = f"  {rw} × {rh}  "
        info_y = ry - 24 if ry > 32 else ry + rh + 6
        self._info_id = self.canvas.create_text(
            rx + 2, info_y,
            text=info_text,
            anchor=tk.NW,
            fill='white',
            font=('Microsoft YaHei UI', 10),
        )
        # 标签背景
        bbox = self.canvas.bbox(self._info_id)
        if bbox:
            self._info_bg_id = self.canvas.create_rectangle(
                bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 4,
                fill='#333333', outline='',
            )
            self.canvas.tag_lower(self._info_bg_id, self._info_id)

    def _on_release(self, event):
        if self._start_x is None:
            return

        x1, y1 = self._start_x, self._start_y
        x2, y2 = event.x, event.y
        rx = min(x1, x2)
        ry = min(y1, y2)
        rw = abs(x2 - x1)
        rh = abs(y2 - y1)

        self.win.destroy()

        if rw < 10 or rh < 10:
            self._result = None
        else:
            left, top, _, _ = _get_virtual_screen_rect()
            self._result = {
                "image": self._full_img.crop((rx, ry, rx + rw, ry + rh)),
                "x": left + rx,
                "y": top + ry,
                "w": rw,
                "h": rh,
            }

    def _on_cancel(self, event=None):
        self.win.destroy()
        self._result = None
