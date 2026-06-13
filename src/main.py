"""
ScreenTool 入口模块
- 系统托盘图标（pystray）
- 全局热键 Ctrl+Alt+X
- 截图 → 颜色提取 → OCR → 结果展示
"""
import os
import sys
import time
import threading
import atexit
import tkinter as tk
from tkinter import messagebox

# ── 第三方库 ──
import pystray
from PIL import Image, ImageDraw

# ── 项目模块 ──
from screen_capture import ScreenCapture
from color_extractor import extract_colors
from ocr_engine import recognize_text, is_ocr_ready, get_ocr_error
from result_window import ResultWindow
from clipboard_helper import copy_text, copy_image


# ── 路径处理（PyInstaller 兼容） ──
def _base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# ── 托盘图标生成 ──
def _create_icon_image(size=64):
    """用 PIL 绘制一个剪刀图标"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = size // 6

    # 底色圆
    draw.ellipse([margin, margin, size - margin, size - margin], fill="#4A90D9")

    # 剪刀形状（简化为十字准星）
    cx, cy = size // 2, size // 2
    arm = size // 4
    lw = max(2, size // 16)

    # 十字准星
    draw.rectangle([cx - lw // 2, cy - arm, cx + lw // 2, cy + arm], fill="white")
    draw.rectangle([cx - arm, cy - lw // 2, cx + arm, cy + lw // 2], fill="white")

    # 中心点
    r = size // 12
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#4A90D9")

    return img


# ════════════════════════════════════════════
# 主应用类
# ════════════════════════════════════════════

class ScreenToolApp:
    def __init__(self):
        # Tk 根窗口（隐藏）
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("ScreenTool")

        # 状态
        self._running = True
        self._tray = None
        self._capturing = False  # 防重入标志（替代跨线程Lock）

        # 子模块
        self.result_window = ResultWindow(self._root)

        # 启动
        self._init_tray()
        self._init_hotkey()

    # ── 系统托盘 ──

    def _init_tray(self):
        icon_img = _create_icon_image(64)
        menu = pystray.Menu(
            pystray.MenuItem("截屏 (Ctrl+Alt+X)", self._on_tray_capture, default=True),
            pystray.MenuItem("关于", self._on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._on_exit),
        )
        self._tray = pystray.Icon(
            "ScreenTool",
            icon_img,
            "ScreenTool - 截屏工具箱",
            menu,
        )

        # pystray 在独立线程运行
        tray_thread = threading.Thread(target=self._tray.run, daemon=True)
        tray_thread.start()

    # ── 全局热键 ──

    def _init_hotkey(self):
        """注册 Ctrl+Alt+X 热键"""
        try:
            import keyboard

            def on_hotkey():
                # 防重入
                if self._capturing:
                    return
                self._capturing = True
                # 短暂延迟让修饰键释放
                time.sleep(0.12)
                # 调度到主线程执行
                self._root.after(0, self._do_capture)

            keyboard.add_hotkey("ctrl+alt+x", on_hotkey)
        except ImportError:
            messagebox.showerror("错误", "需要 keyboard 库，请运行: pip install keyboard")

    # ── 截图流程 ──

    def _do_capture(self):
        """主线程截图 + 处理 + 展示"""
        try:
            capturer = ScreenCapture(self._root)
            result = capturer.capture()

            if result is None:
                return  # 用户取消

            screenshot = result["image"]

            # 1. 复制截图到剪贴板
            copy_image(screenshot)

            # 2. 提取主要颜色
            colors = extract_colors(screenshot)

            # 3. OCR 识别（后台线程，不阻塞 UI）
            ocr_text = "识别中…"
            self.result_window.show(screenshot, colors, ocr_text)

            # 异步执行 OCR
            threading.Thread(
                target=self._run_ocr,
                args=(screenshot,),
                daemon=True,
            ).start()

        finally:
            self._capturing = False

    def _run_ocr(self, screenshot):
        """后台线程执行 OCR"""
        try:
            ocr_text = recognize_text(screenshot)
        except Exception as e:
            ocr_text = f"[OCR 异常: {e}]"

        # 回到主线程更新 UI
        self._root.after(0, lambda: self._update_ocr_result(ocr_text))

    def _update_ocr_result(self, ocr_text: str):
        """主线程更新 OCR 结果（通过存储的 Text 控件引用直接更新）"""
        self.result_window._ocr_text = ocr_text

        rw = self.result_window
        widget = rw._ocr_text_widget
        if widget is None:
            return
        try:
            import tkinter as tk
            widget.config(state=tk.NORMAL)
            widget.delete('1.0', tk.END)
            widget.insert('1.0', ocr_text)
            lines = max(3, min(15, ocr_text.count('\n') + 2))
            widget.config(height=lines, state=tk.DISABLED)
        except Exception:
            pass

    # ── 托盘菜单回调 ──

    def _on_tray_capture(self, icon, item):
        """托盘菜单触发截图"""
        if self._capturing:
            return
        self._capturing = True
        self._root.after(100, self._do_capture)

    def _on_about(self, icon, item):
        messagebox.showinfo(
            "关于 ScreenTool",
            "ScreenTool - 截屏工具箱 v1.0\n\n"
            "框选截屏 + 颜色提取 + OCR 文字识别\n\n"
            "快捷键: Ctrl+Alt+X\n"
            "GitHub: user-henry/screen-tool",
        )

    def _on_exit(self, icon, item):
        self._shutdown()

    # ── 生命周期 ──

    def run(self):
        """启动应用（阻塞主线程直到退出）"""
        atexit.register(self._shutdown)
        self._root.mainloop()

    def _shutdown(self):
        if not self._running:
            return
        self._running = False

        try:
            if self._tray:
                self._tray.stop()
        except Exception:
            pass

        try:
            self._root.quit()
            self._root.destroy()
        except Exception:
            pass


# ════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════

def main():
    # 单实例检测
    import ctypes
    mutex_name = "ScreenTool_SingleInstance"
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, mutex_name)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        messagebox.showinfo("ScreenTool", "ScreenTool 已经在运行中。\n请在系统托盘找到图标操作。")
        return

    app = ScreenToolApp()
    app.run()


if __name__ == "__main__":
    main()
