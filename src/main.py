"""
ScreenTool 入口模块 v2

- 系统托盘图标（pystray）+ 全局热键
- 框选截屏 → 复制剪贴板 → 主色提取 → OCR 识别 → 结果面板
- 截图自动保存到本地历史记录，支持随时查看 / 命名 / 分类 / 粘贴 / 删除
- 画笔批注：直接在截图上做标注
- 设置页面：所有偏好本地保存，重启后依然生效

交互要点：所有 GUI 操作都通过动作队列回到 tkinter 主线程执行，
托盘线程与热键线程只负责投递动作，避免跨线程操作 Tk 控件。
"""

import os
import queue
import sys
import threading
import atexit
import tkinter as tk

# ── 第三方库 ──
import pystray
from PIL import Image, ImageDraw

# ── 项目模块 ──
from app_settings import AppSettings, APP_VERSION
from history_manager import HistoryManager
from history_window import HistoryWindow
from result_window import ResultWindow
from settings_window import SettingsWindow
from screen_capture import ScreenCapture
from paint_window import PaintWindow
from rope_window import RopeWindow
from color_extractor import extract_colors
from ocr_engine import recognize_text
from clipboard_helper import copy_text, copy_image
import ui_theme
from ui_theme import toast


APP_TITLE = "ScreenTool - 截屏工具箱"


def _enable_dpi_awareness():
    """让截图在缩放显示器上保持清晰（失败不影响运行）"""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # 系统 DPI 感知
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ════════════════════════════════════════════
# 托盘图标
# ════════════════════════════════════════════

def _create_icon_image(size=64):
    """绘制一个科技风的截图图标（准星 + 选框）"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    box = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(box, radius=size // 8, fill="#0B1020", outline="#3DE1FF", width=2)

    # 四角标记
    arm = size // 4
    lw = max(2, size // 14)
    x1, y1, x2, y2 = box
    for px, py, dx, dy in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        draw.line([px, py, px + dx * arm, py], fill="#3DE1FF", width=lw)
        draw.line([px, py, px, py + dy * arm], fill="#3DE1FF", width=lw)

    # 中心准星
    cx, cy = size // 2, size // 2
    r = max(2, size // 10)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#7C5CFF")
    return img


# ════════════════════════════════════════════
# 主应用
# ════════════════════════════════════════════

class ScreenToolApp:

    def __init__(self):
        _enable_dpi_awareness()

        # Tk 根窗口（隐藏）
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("ScreenTool")

        # 设置 / 历史
        self.settings = AppSettings()
        self.history = HistoryManager(self.settings)

        # 状态
        self._running = True
        self._capturing = False
        self._tray = None
        self._hotkey_handles = {}
        self._actions = queue.Queue()
        self._ocr_token = 0
        self._paint_windows = []
        self._clipboard_backup = None

        try:
            ui_theme.apply(self._root, self.settings.get("accent"))
        except Exception:
            pass

        # 子窗口 / 面板
        self.result_window = ResultWindow(
            self._root, self.settings, self.history,
            callbacks={
                "paint": self.open_paint,
                "history": lambda: self.open_history(),
                "settings": self.open_settings,
                "on_changed": self._on_data_changed,
            },
        )
        self.history_window = HistoryWindow(
            self._root, self.settings, self.history,
            callbacks={
                "paste": self.paste_history,
                "paint": lambda entry: self.open_paint(None, entry),
                "settings": self.open_settings,
                "on_changed": self._on_data_changed,
                "on_close": lambda: None,
            },
        )
        self.settings_window = SettingsWindow(
            self._root, self.settings, self.history,
            on_apply=self._on_settings_applied,
        )

        # 屏幕顶部的「绳子」：截图后自动挂上去
        self.rope = RopeWindow(
            self._root, self.settings, self.history,
            callbacks={
                "paste": self.paste_history,
                "paint": lambda entry: self.open_paint(None, entry),
                "history": lambda: self.open_history(),
                "delete": self.delete_entry,
                "on_changed": self._on_data_changed,
            },
        )
        try:
            self.rope.reload()
        except Exception:
            pass

        # 启动
        self._init_tray()
        self._register_hotkeys()
        self._root.after(120, self._poll_actions)

        # 首次运行提示
        self._root.after(900, self._first_run_hint)

    # ════════════════════════════════
    # 动作队列（线程安全）
    # ════════════════════════════════

    def _post(self, action: str, *args):
        """从任意线程投递一个动作，主线程轮询执行"""
        try:
            self._actions.put((action, args))
        except Exception:
            pass

    def _poll_actions(self):
        """主线程轮询动作队列"""
        while True:
            try:
                action, args = self._actions.get_nowait()
            except queue.Empty:
                break
            try:
                self._dispatch(action, *args)
            except Exception:
                pass
        if self._running:
            try:
                self._root.after(70, self._poll_actions)
            except Exception:
                pass

    def _dispatch(self, action: str, *args):
        handlers = {
            "capture": self._trigger_capture,
            "history": self.open_history,
            "settings": self.open_settings,
            "paste_last": self.paste_last,
            "rope_toggle": self._toggle_rope,
            "about": self._show_about,
            "exit": self._shutdown,
            "tray_refresh": self._update_tray,
            "ocr_done": self._on_ocr_done,
        }
        handler = handlers.get(action)
        if handler:
            handler(*args)

    # ════════════════════════════════
    # 系统托盘
    # ════════════════════════════════

    def _init_tray(self):
        try:
            self._tray = pystray.Icon("ScreenTool", _create_icon_image(64),
                                      APP_TITLE, menu=self._build_tray_menu())
            threading.Thread(target=self._run_tray, daemon=True).start()
        except Exception:
            self._tray = None

    def _run_tray(self):
        try:
            self._tray.run()
        except Exception:
            pass

    def _build_tray_menu(self):
        hk_capture = self.settings.get("hotkey_capture") or ""
        hk_history = self.settings.get("hotkey_history") or ""
        hk_last = self.settings.get("hotkey_paste_last") or ""
        return pystray.Menu(
            pystray.MenuItem(f"截屏  ({hk_capture})" if hk_capture else "截屏",
                             lambda: self._post("capture"), default=True),
            pystray.MenuItem(f"历史截图  ({hk_history})" if hk_history else "历史截图",
                             lambda: self._post("history")),
            pystray.MenuItem(f"粘贴最近一张  ({hk_last})" if hk_last else "粘贴最近一张",
                             lambda: self._post("paste_last")),
            pystray.MenuItem("显示 / 收起绳子", lambda: self._post("rope_toggle")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("设置", lambda: self._post("settings")),
            pystray.MenuItem("关于", lambda: self._post("about")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda: self._post("exit")),
        )

    def _update_tray(self):
        if not self._tray:
            return
        try:
            count = self.history.count()
            self._tray.title = f"{APP_TITLE} - 历史 {count} 张"
            self._tray.menu = self._build_tray_menu()
        except Exception:
            pass

    # ════════════════════════════════
    # 全局热键
    # ════════════════════════════════

    def _register_hotkeys(self):
        """按设置注册全局热键（会先清理旧的注册）"""
        try:
            import keyboard
        except ImportError:
            return ["缺少 keyboard 库，全局快捷键不可用（pip install keyboard）"]

        for handle in self._hotkey_handles.values():
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._hotkey_handles = {}

        mapping = [
            ("hotkey_capture", "截屏", "capture"),
            ("hotkey_history", "历史截图", "history"),
            ("hotkey_paste_last", "粘贴最近一张截图", "paste_last"),
            ("hotkey_settings", "设置", "settings"),
        ]
        errors = []
        for key, label, action in mapping:
            hotkey = (self.settings.get(key) or "").strip()
            if not hotkey:
                continue
            try:
                handle = keyboard.add_hotkey(
                    hotkey, lambda a=action: self._post(a), suppress=False)
                self._hotkey_handles[key] = handle
            except Exception as e:
                errors.append(f"{label}（{hotkey}）注册失败：{e}")
        return errors

    # ════════════════════════════════
    # 截图流程
    # ════════════════════════════════

    def _trigger_capture(self):
        """热键 / 托盘触发截图（稍作延迟，等待按键释放）"""
        if self._capturing:
            return
        self._capturing = True
        self._root.after(160, self._do_capture)

    def _do_capture(self):
        """主线程截图 + 处理 + 展示"""
        try:
            capturer = ScreenCapture(self._root, self.settings)
            result = capturer.capture()
            if result is None:
                return

            image = result["image"]
            if image.width < 2 or image.height < 2:
                return

            # 1. 复制到剪贴板
            if self.settings.get("auto_copy_image", True):
                copy_image(image)

            # 2. 主色提取
            colors = []
            try:
                max_colors = int(self.settings.get("max_colors", 8) or 8)
                colors = extract_colors(image, max_colors=max(2, min(16, max_colors)))
            except Exception:
                colors = []

            # 3. 保存到历史记录
            entry = None
            if self.settings.get("save_history", True):
                try:
                    entry = self.history.add(
                        image,
                        colors=[c.get("hex") for c in colors],
                        source="capture",
                    )
                except Exception:
                    entry = None

            # 4. 提示
            if self.settings.get("show_toast", True):
                msg = f"{image.width} × {image.height}"
                if entry:
                    msg += f"　·　已保存到历史（{self.history.count()} 张）"
                toast(self._root, "截图完成", msg, kind="success")

            # 4.1 挂到绳子
            if entry is not None:
                try:
                    if self.rope.add_entry(entry) and self.settings.get("show_toast", True):
                        toast(self._root, "已挂到绳子",
                              "把图片拖到其它窗口即可粘贴", kind="info", duration=2600)
                except Exception:
                    pass

            self._update_tray()

            # 5. OCR（异步）
            ocr_enabled = bool(self.settings.get("ocr_enabled", True))
            self._ocr_token += 1
            token = self._ocr_token

            # 6. 结果面板
            if self.settings.get("show_result_window", True):
                try:
                    self.result_window.show(
                        image, colors,
                        "识别中…" if ocr_enabled else "",
                        entry=entry,
                    )
                except Exception:
                    pass

            if ocr_enabled:
                threading.Thread(target=self._run_ocr, args=(image, token,
                                                             entry.get("id") if entry else None),
                                 daemon=True).start()

        finally:
            self._capturing = False

    # ── OCR 后台线程 ──

    def _run_ocr(self, image, token: int, entry_id):
        try:
            text = recognize_text(image)
        except Exception as e:
            text = f"[OCR 异常: {e}]"
        self._post("ocr_done", token, entry_id, text)

    def _on_ocr_done(self, token: int, entry_id, text: str):
        """主线程接收 OCR 结果"""
        if entry_id and self.settings.get("ocr_save_to_history", True):
            try:
                self.history.attach_ocr(entry_id, ocr_text=text)
            except Exception:
                pass
        if self.result_window.is_open():
            try:
                self.result_window.set_ocr_text(text)
            except Exception:
                pass

    # ════════════════════════════════
    # 历史截图
    # ════════════════════════════════

    def open_history(self, category: str = None):
        try:
            self.history_window.show(category=category)
        except Exception as e:
            toast(self._root, "无法打开历史窗口", str(e), kind="error")

    def paste_history(self, entry: dict, auto: bool = False):
        """把历史截图复制到剪贴板；auto=True 时尝试自动 Ctrl+V"""
        if not entry:
            return
        image = self.history.image_of(entry)
        if image is None:
            toast(self._root, "图片文件已丢失", entry.get("title", ""), kind="error")
            return

        if self.settings.get("restore_clipboard", False):
            self._backup_clipboard()

        if not copy_image(image):
            toast(self._root, "复制失败", "请重试", kind="error")
            return

        title = entry.get("title", "")
        if not auto:
            toast(self._root, "已复制历史截图", f"{title}　·　现在可以 Ctrl+V 粘贴", kind="success")
            return

        toast(self._root, "正在粘贴…", title, kind="info")
        self._auto_paste()

    def paste_last(self):
        """把最近一张历史截图复制到剪贴板"""
        entry = self.history.latest()
        if not entry:
            toast(self._root, "还没有历史截图", "先按快捷键截一张图吧", kind="warn")
            return
        self.paste_history(entry, auto=True)

    def _auto_paste(self):
        """隐藏自身窗口后模拟 Ctrl+V"""
        try:
            if self.history_window and self.history_window.win:
                self.history_window.win.iconify()
        except Exception:
            pass
        try:
            if self.result_window.win:
                self.result_window.win.iconify()
        except Exception:
            pass

        def send():
            try:
                import keyboard
                keyboard.send("ctrl+v")
            except Exception:
                pass
            if self.settings.get("restore_clipboard", False):
                self._root.after(1500, self._restore_clipboard)

        self._root.after(420, send)

    def _backup_clipboard(self):
        try:
            import pyperclip
            self._clipboard_backup = pyperclip.paste() or None
        except Exception:
            self._clipboard_backup = None

    def _restore_clipboard(self):
        if not self._clipboard_backup:
            return
        try:
            copy_text(self._clipboard_backup)
        except Exception:
            pass
        self._clipboard_backup = None

    # ════════════════════════════════
    # 画笔批注
    # ════════════════════════════════

    def open_paint(self, image=None, entry: dict = None):
        """打开画笔窗口（可按图片或按历史记录）"""
        if image is None and entry:
            image = self.history.image_of(entry)
            if image is None:
                toast(self._root, "无法打开批注", "图片文件已丢失", kind="error")
                return
        if image is None:
            recent = self.history.latest()
            if recent:
                entry = entry or recent
                image = self.history.image_of(recent)
        if image is None:
            toast(self._root, "没有可批注的图片", "先截一张图试试", kind="warn")
            return

        title = f"批注 - {entry.get('title', '')}" if entry else "批注新截图"
        try:
            window = PaintWindow(
                self._root, image, self.settings, title=title,
                entry=entry, history=self.history,
                on_saved=lambda action, img, ent: self._on_data_changed(),
            )
            self._paint_windows = [w for w in self._paint_windows
                                   if getattr(w, "win", None) and w.win.winfo_exists()]
            self._paint_windows.append(window)
        except Exception as e:
            toast(self._root, "无法打开画笔窗口", str(e), kind="error")

    # ════════════════════════════════
    # 设置
    # ════════════════════════════════

    def open_settings(self):
        try:
            self.settings_window.show()
        except Exception as e:
            toast(self._root, "无法打开设置窗口", str(e), kind="error")

    def _on_settings_applied(self, settings, info: dict = None):
        """设置保存后的即时生效逻辑"""
        # 1. 历史目录变化 → 切换存储
        info = info or {}
        old_dir = info.get("old_history_dir")
        new_dir = info.get("new_history_dir") or settings.history_dir()
        if old_dir and old_dir != new_dir:
            try:
                self.history.attach_base(new_dir)
            except Exception:
                pass

        # 2. 重新注册热键
        errors = self._register_hotkeys()
        if errors:
            for err in errors:
                toast(self._root, "快捷键注册失败", err, kind="error")
            try:
                self.settings_window.set_status("部分快捷键注册失败，请更换其它组合")
            except Exception:
                pass

        # 3. 主题色
        try:
            ui_theme.apply(self._root, settings.get("accent"))
        except Exception:
            pass

        # 4. 托盘与历史窗口
        self._update_tray()
        try:
            if self.history_window.win and self.history_window.win.winfo_exists():
                self.history_window.refresh()
        except Exception:
            pass

        # 5. 绳子（位置 / 开关 / 毛玻璃都会即时生效）
        try:
            self.rope.refresh_settings()
        except Exception:
            pass

    def _on_data_changed(self):
        """历史数据变化后的统一处理"""
        self._update_tray()
        try:
            self.rope.reload()
        except Exception:
            pass

    def _toggle_rope(self):
        """托盘菜单：展开 / 收起绳子"""
        try:
            if self.rope.win is None or not self.rope.win.winfo_exists():
                self.rope.reload()
                self.rope.show()
            else:
                self.rope.toggle()
        except Exception as e:
            toast(self._root, "绳子操作失败", str(e), kind="error")

    def delete_entry(self, entry: dict):
        """删除一条历史记录（绳子右键菜单调用）"""
        if not entry:
            return
        from tkinter import messagebox
        if self.settings.get("confirm_delete", True):
            title = entry.get("title") or "该截图"
            if not messagebox.askyesno("确认删除",
                                       f"确定删除「{title}」吗？\n此操作不可撤销。"):
                return
        try:
            self.history.delete(entry.get("id"))
        except Exception:
            pass
        self._on_data_changed()

    # ════════════════════════════════
    # 其它
    # ════════════════════════════════

    def _first_run_hint(self):
        if not self.settings.get("show_toast", True):
            return
        hotkey = self.settings.get("hotkey_capture") or "ctrl+alt+x"
        toast(self._root, "ScreenTool 已启动",
              f"按 {hotkey.upper()} 开始截图　·　右键托盘图标可打开历史与设置",
              kind="info", duration=4200)

    def _show_about(self):
        from tkinter import messagebox
        hotkey = (self.settings.get("hotkey_capture") or "").upper()
        history_hk = (self.settings.get("hotkey_history") or "").upper()
        messagebox.showinfo(
            "关于 ScreenTool",
            f"ScreenTool - 截屏工具箱 v{APP_VERSION}\n\n"
            f"框选截屏 · 颜色提取 · OCR 文字识别\n"
            f"历史截图 · 画笔批注 · 本地设置\n\n"
            f"截图快捷键：{hotkey or '（未设置）'}\n"
            f"历史快捷键：{history_hk or '（未设置）'}\n\n"
            f"数据目录：{self.history.base_dir}\n"
            f"历史记录：{self.history.count()} 张",
        )

    # ════════════════════════════════
    # 生命周期
    # ════════════════════════════════

    def run(self):
        atexit.register(self._shutdown)
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _shutdown(self):
        if not self._running:
            return
        self._running = False

        try:
            ui_theme.close_all_toasts()
        except Exception:
            pass
        try:
            if self._tray:
                self._tray.stop()
        except Exception:
            pass
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        self._cleanup()

        try:
            self._root.quit()
            self._root.destroy()
        except Exception:
            pass

    def _cleanup(self):
        try:
            self.rope.destroy()
        except Exception:
            pass
        for closer in ("hide",):
            try:
                getattr(self.history_window, closer)()
            except Exception:
                pass
        for window in list(self._paint_windows):
            try:
                window.win.destroy()
            except Exception:
                pass


# ════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════

def _single_instance_guard():
    """单实例检测，返回 (是否已存在, 互斥句柄)"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "ScreenTool_SingleInstance_v2")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return True, handle
        return False, handle
    except Exception:
        return False, None


def main():
    already, _handle = _single_instance_guard()
    if already:
        try:
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("ScreenTool", "ScreenTool 已经在运行中。\n请在系统托盘找到图标操作。")
            root.destroy()
        except Exception:
            pass
        return

    # 允许从任意工作目录启动
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        app = ScreenToolApp()
    except Exception as e:
        try:
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("ScreenTool 启动失败", str(e))
            root.destroy()
        except Exception:
            print(f"ScreenTool 启动失败: {e}")
        return

    app.run()


if __name__ == "__main__":
    main()
