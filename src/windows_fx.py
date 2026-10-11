r"""
Windows 原生窗口特效封装

提供：
- 毛玻璃（blur-behind / acrylic，走 DWM 合成，真模糊窗口背后的内容）
- 圆角窗口、工具窗口、置顶不抢焦点（WS_EX_NOACTIVATE）
- 全局鼠标捕获（拖拽到窗口外仍能收到移动事件）
- 光标下的窗口查询（判断“拖到了哪个应用”）

所有函数在非 Windows 或调用失败时安全降级为 no-op，绝不抛异常。
"""

import ctypes
import sys

IS_WINDOWS = sys.platform == "win32"

# ── SetWindowCompositionAttribute 相关 ──
WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

# ── 窗口扩展样式 ──
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

# ── DWM 圆角 ──
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

GA_ROOT = 2

# 桌面的“非应用”窗口类名：拖到这些地方不算拖到应用
DESKTOP_CLASSES = {
    "progman", "workerw", "shell_traywnd", "shell_secondarytraywnd",
    "syslistview32", "shelldll_defview", "tooltips_class32",
}


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),      # ABGR
        ("AnimationId", ctypes.c_int),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


if IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _dwmapi = ctypes.windll.dwmapi
    try:
        _set_wca = _user32.SetWindowCompositionAttribute
        _set_wca.restype = ctypes.c_int
    except Exception:
        _set_wca = None
else:
    _user32 = None
    _dwmapi = None
    _set_wca = None


# ════════════════════════════════════════════
# 句柄工具
# ════════════════════════════════════════════

def hwnd_of(widget) -> int:
    """取得 tkinter 窗口对应的顶层 HWND（失败返回 0）"""
    if not IS_WINDOWS:
        return 0
    try:
        wid = widget.winfo_id()
        root = _user32.GetAncestor(wid, GA_ROOT)
        return int(root or wid)
    except Exception:
        return 0


def root_hwnd(hwnd: int) -> int:
    """取任意窗口的顶层窗口句柄"""
    if not IS_WINDOWS or not hwnd:
        return 0
    try:
        return int(_user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
    except Exception:
        return 0


def _abgr(hex_color: str, alpha: int) -> int:
    """#RRGGBB + alpha(0-255) → ABGR 整数（DWM 要求 ABGR 顺序）"""
    try:
        value = (hex_color or "#0B1020").lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except Exception:
        r, g, b = 11, 16, 32
    a = max(0, min(255, int(alpha)))
    return (a << 24) | (b << 16) | (g << 8) | r


# ════════════════════════════════════════════
# 毛玻璃
# ════════════════════════════════════════════

def enable_blur(widget, tint: str = "#0B1020", tint_alpha: int = 0x66,
                mode: str = "blur") -> bool:
    """
    给窗口开启毛玻璃背景（窗口背后的内容会被真实模糊）。

    Args:
        widget: 任意 tkinter 窗口
        tint: 玻璃染色（#RRGGBB）
        tint_alpha: 染色不透明度 0-255，越大越暗越实
        mode: "blur"（平滑，推荐）/ "acrylic"（更亮，Win10 上移动可能掉帧）
    """
    if not IS_WINDOWS or _set_wca is None:
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False

    state = ACCENT_ENABLE_ACRYLICBLURBEHIND if mode == "acrylic" else ACCENT_ENABLE_BLURBEHIND
    try:
        policy = ACCENT_POLICY()
        policy.AccentState = state
        policy.AccentFlags = 0x20 | 0x40 | 0x80 | 0x100   # 四边都生效
        policy.GradientColor = _abgr(tint, tint_alpha)
        policy.AnimationId = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)
        _set_wca(hwnd, ctypes.byref(data))
        return True
    except Exception:
        return False


def disable_blur(widget) -> bool:
    """关闭毛玻璃"""
    if not IS_WINDOWS or _set_wca is None:
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False
    try:
        policy = ACCENT_POLICY()
        policy.AccentState = ACCENT_DISABLED
        policy.AccentFlags = 0
        policy.GradientColor = 0
        policy.AnimationId = 0
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)
        _set_wca(hwnd, ctypes.byref(data))
        return True
    except Exception:
        return False


def set_rounded(widget, preference: int = DWMWCP_ROUND) -> bool:
    """Win11 圆角窗口（Win10 忽略）"""
    if not IS_WINDOWS:
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False
    try:
        value = ctypes.c_int(preference)
        _dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(value), ctypes.sizeof(value))
        return True
    except Exception:
        return False


# ════════════════════════════════════════════
# 窗口行为
# ════════════════════════════════════════════

def _set_ex_style(widget, add: int = 0, remove: int = 0) -> bool:
    if not IS_WINDOWS:
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False
    try:
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | add) & ~remove
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        return True
    except Exception:
        return False


def set_no_activate(widget, enabled: bool = True) -> bool:
    """点击窗口不抢焦点（拖拽时目标应用仍保持焦点，粘贴才不会打错地方）"""
    if enabled:
        return _set_ex_style(widget, add=WS_EX_NOACTIVATE)
    return _set_ex_style(widget, remove=WS_EX_NOACTIVATE)


def set_tool_window(widget, enabled: bool = True) -> bool:
    """工具窗口：不在任务栏 / Alt-Tab 中出现"""
    if enabled:
        return _set_ex_style(widget, add=WS_EX_TOOLWINDOW)
    return _set_ex_style(widget, remove=WS_EX_TOOLWINDOW)


def apply_glass(widget, *, tint: str = "#0B1020", tint_alpha: int = 0x66,
                mode: str = "blur", alpha: float = None, rounded: bool = False,
                no_activate: bool = False, tool_window: bool = False) -> bool:
    """一站式：毛玻璃 +（可选）整体透明度 / 圆角 / 不抢焦点 / 工具窗口。"""
    ok = False
    try:
        if alpha is not None:
            widget.attributes("-alpha", float(alpha))
    except Exception:
        pass
    ok = enable_blur(widget, tint=tint, tint_alpha=tint_alpha, mode=mode) or ok
    if rounded:
        set_rounded(widget)
    if no_activate:
        set_no_activate(widget, True)
    if tool_window:
        set_tool_window(widget, True)
    return ok


def begin_capture(widget) -> bool:
    """开始全局鼠标捕获：拖拽到窗口外仍能收到移动事件"""
    if not IS_WINDOWS:
        return False
    hwnd = hwnd_of(widget)
    if not hwnd:
        return False
    try:
        _user32.SetCapture(hwnd)
        return True
    except Exception:
        return False


def end_capture() -> bool:
    """结束鼠标捕获"""
    if not IS_WINDOWS:
        return False
    try:
        _user32.ReleaseCapture()
        return True
    except Exception:
        return False


# ════════════════════════════════════════════
# 光标与窗口查询
# ════════════════════════════════════════════

def cursor_pos():
    """当前鼠标位置 (x, y)（屏幕坐标）"""
    try:
        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)
    except Exception:
        return 0, 0


def screen_geometry():
    """主显示器尺寸 (left, top, width, height)"""
    try:
        width = _user32.GetSystemMetrics(0)
        height = _user32.GetSystemMetrics(1)
        return 0, 0, int(width), int(height)
    except Exception:
        return 0, 0, 1280, 720


def window_under_cursor():
    """
    光标下的窗口信息。

    Returns:
        dict(hwnd, root, class_name, title, is_desktop)
    """
    info = {"hwnd": 0, "root": 0, "class_name": "", "title": "",
            "is_desktop": True}
    if not IS_WINDOWS:
        return info
    try:
        pt = POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        hwnd = _user32.WindowFromPoint(pt)
        if not hwnd:
            return info

        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        class_name = buf.value or ""

        root = int(_user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
        tbuf = ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(root, tbuf, 512)

        info["hwnd"] = int(hwnd)
        info["root"] = root
        info["class_name"] = class_name
        info["title"] = tbuf.value or ""
        info["is_desktop"] = class_name.lower() in DESKTOP_CLASSES
    except Exception:
        pass
    return info


def is_own_window(hwnd: int, widgets) -> bool:
    """判断某个窗口是否属于本程序"""
    if not hwnd:
        return False
    target = root_hwnd(hwnd)
    if not target:
        return False
    for widget in widgets or ():
        try:
            if hwnd_of(widget) == target:
                return True
        except Exception:
            continue
    return False
