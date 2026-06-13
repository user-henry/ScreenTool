"""
OCR 引擎模块
- 使用 PaddleOCR 3.7（ONNX Runtime 引擎）进行离线文字识别
- 根据检测框坐标保留原排版（换行、缩进）
- 模型文件与 EXE 同目录分发（models/official_models/），无需联网下载
"""
import os
import sys
import logging
import threading

# 抑制 PaddleOCR / paddlex 内部日志
for _log_name in ("ppocr", "paddleocr", "paddlex", "modelscope"):
    logging.getLogger(_log_name).setLevel(logging.ERROR)

_ocr_instance = None
_ocr_lock = threading.Lock()
_ocr_ready = False
_ocr_error = None


def _get_model_root() -> str:
    """
    返回模型缓存根目录。
    - 开发模式：使用 ~/.paddlex（PaddleOCR 默认下载位置）
    - 打包模式：使用 EXE 同目录下的 models/（构建后手动复制到 release/）
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包：模型在 EXE 同目录下的 models/ 中
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'models')
    else:
        # 开发模式：使用系统默认缓存
        return os.path.join(os.path.expanduser('~'), '.paddlex')


def _get_ocr():
    """获取 OCR 实例（懒加载 + 线程安全）"""
    global _ocr_instance, _ocr_ready, _ocr_error

    if _ocr_ready:
        return _ocr_instance
    if _ocr_error:
        return None

    with _ocr_lock:
        if _ocr_ready:
            return _ocr_instance
        if _ocr_error:
            return None

        try:
            from paddleocr import PaddleOCR

            model_root = _get_model_root()
            os.environ['PADDLE_PDX_HOME'] = model_root
            os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

            _ocr_instance = PaddleOCR(
                lang='ch',
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                engine='onnxruntime',
            )
            _ocr_ready = True
            return _ocr_instance
        except Exception as e:
            _ocr_error = str(e)
            return None


def _build_text_with_layout(result, image_width: int) -> str:
    """
    根据 PaddleOCR 3.7 predict() 结果重建带排版的文本。
    """
    if not result or not isinstance(result, list) or len(result) == 0:
        return ""

    page = result[0]
    texts = page.get('rec_texts', [])
    polys = page.get('dt_polys', [])
    if not texts:
        return ""

    items = []
    for i, (text, poly) in enumerate(zip(texts, polys)):
        if not text or not text.strip():
            continue
        top_y = int(poly[0][1])
        bottom_y = int(poly[2][1])
        left_x = int(poly[0][0])
        height = bottom_y - top_y
        items.append({
            "text": text,
            "top_y": top_y,
            "left_x": left_x,
            "height": height,
        })

    if not items:
        return ""

    items.sort(key=lambda it: it["top_y"])

    heights = [it["height"] for it in items if it["height"] > 0]
    avg_height = sum(heights) / len(heights) if heights else 20
    avg_char_width = 8

    lines = []
    current_line = [items[0]]
    prev_y = items[0]["top_y"]

    for item in items[1:]:
        y_diff = item["top_y"] - prev_y
        if y_diff > avg_height * 0.5:
            lines.append(current_line)
            current_line = [item]
        else:
            current_line.append(item)
        prev_y = item["top_y"]

    if current_line:
        lines.append(current_line)

    text_lines = []
    all_left = [it["left_x"] for ln in lines for it in ln]
    base_x = min(all_left) if all_left else 0

    for line_items in lines:
        line_items.sort(key=lambda it: it["left_x"])
        line_text = ""
        prev_right = base_x

        for item in line_items:
            x_diff = item["left_x"] - prev_right
            if x_diff > avg_char_width * 1.5:
                spaces = max(1, round(x_diff / avg_char_width))
                line_text += " " * spaces
            elif x_diff > 2:
                line_text += " "
            line_text += item["text"]
            text_pixel_width = len(item["text"]) * avg_char_width
            prev_right = item["left_x"] + text_pixel_width

        first_left = line_items[0]["left_x"]
        indent_spaces = max(0, round((first_left - base_x) / avg_char_width))
        if indent_spaces > 0:
            line_text = " " * indent_spaces + line_text

        text_lines.append(line_text)

    return "\n".join(text_lines)


def recognize_text(image) -> str:
    """
    识别图像中的文字，保留排版。
    """
    ocr = _get_ocr()
    if ocr is None:
        err_msg = _ocr_error or "OCR 模型未初始化"
        return f"[OCR 错误: {err_msg}]"

    try:
        import numpy as np
        img_array = np.array(image.convert("RGB"))
        results = ocr.predict(img_array)

        if not results or len(results) == 0:
            return ""

        width = image.width
        return _build_text_with_layout(results, width)

    except Exception as e:
        return f"[OCR 识别失败: {e}]"


def is_ocr_ready() -> bool:
    """检查 OCR 是否已初始化完成"""
    return _ocr_ready


def get_ocr_error() -> str:
    """获取 OCR 初始化错误信息"""
    return _ocr_error or ""
