"""
剪贴板操作助手
- 写入文本到系统剪贴板
- 写入图像到系统剪贴板（纯 ctypes 调用 Windows API，无需 pywin32）
"""
import io
import ctypes
import ctypes.wintypes as w
from PIL import Image

import pyperclip


def copy_text(text: str) -> bool:
    """将文本复制到系统剪贴板"""
    if not text or not text.strip():
        return False
    pyperclip.copy(text)
    return True


def copy_image(image: Image.Image) -> bool:
    """
    将 PIL Image 复制到系统剪贴板（DIB 格式）。
    使用纯 ctypes 调用 Windows Clipboard API，不依赖 pywin32。

    原理：
    - 将图片编码为 BMP，去掉 14 字节文件头 → DIB（Device Independent Bitmap）
    - 通过 GlobalAlloc 分配全局内存，SetClipboardData(CF_DIB, ...) 写入剪贴板
    """
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # 显式声明返回类型（64 位兼容，防止指针截断）
        kernel32.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = w.HANDLE
        kernel32.GlobalLock.argtypes = [w.HANDLE]
        kernel32.GlobalLock.restype = w.LPVOID
        kernel32.GlobalUnlock.argtypes = [w.HANDLE]
        kernel32.GlobalFree.argtypes = [w.HANDLE]
        user32.OpenClipboard.argtypes = [w.HWND]
        user32.OpenClipboard.restype = w.BOOL
        user32.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
        user32.SetClipboardData.restype = w.HANDLE

        # —— 编码为 DIB ——
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="BMP")
        bmp = buf.getvalue()
        buf.close()
        dib = bmp[14:]        # 去掉 BMPFILEHEADER（14 字节）
        dib_len = len(dib)

        # —— 分配全局可移动内存 ——
        GHND = 0x0042         # GMEM_MOVEABLE | GMEM_ZEROINIT
        h_mem = kernel32.GlobalAlloc(GHND, dib_len)
        if not h_mem:
            return False

        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            return False

        # 将 DIB 数据拷贝到全局内存
        ctypes.memmove(p_mem, dib, dib_len)
        kernel32.GlobalUnlock(h_mem)

        # —— 写入剪贴板 ——
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_mem)
            return False

        user32.EmptyClipboard()

        CF_DIB = 8  # Windows 预定义剪贴板格式
        if not user32.SetClipboardData(CF_DIB, h_mem):
            kernel32.GlobalFree(h_mem)

        user32.CloseClipboard()
        return True

    except Exception:
        return False
