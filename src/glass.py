r"""
毛玻璃视觉组件（PIL 渲染）

不依赖系统 API：把「玻璃面板 / 相片卡 / 徽章 / 光晕 / 绳子」预先渲染成带透明通道的
图片，再由 tkinter 画到窗口上。配合 windows_fx 的原生模糊，得到真正的磨砂质感。
"""

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ui_theme import COLORS


# ════════════════════════════════════════════
# 基础工具
# ════════════════════════════════════════════

def hex_to_rgb(value: str):
    """#RRGGBB → (r, g, b)"""
    try:
        value = (value or "#000000").lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except Exception:
        return (0, 0, 0)


def mix(color_a, color_b, ratio: float):
    """按比例混合两个 RGB 颜色"""
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(a + (b - a) * ratio) for a, b in zip(color_a, color_b))


def _font(size: int, bold: bool = False):
    """加载中文字体（失败回退默认字体）"""
    names = ("msyhbd.ttc", "msyh.ttc", "msyh.ttf") if bold else \
            ("msyh.ttc", "msyh.ttf", "segoeui.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _rounded_mask(size, radius):
    """圆角矩形遮罩（L 模式）"""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    if radius * 2 >= min(size):
        draw.ellipse([0, 0, size[0] - 1, size[1] - 1], fill=255)
    else:
        draw.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                               radius=radius, fill=255)
    return mask


# ════════════════════════════════════════════
# 玻璃面板
# ════════════════════════════════════════════

def glass_panel(width: int, height: int, *, radius: int = 16,
                top: str = None, bottom: str = None,
                alpha: int = 176, accent: str = None,
                border_alpha: int = 70, glow: bool = True,
                grain: int = 6, shadow: int = 10):
    """
    渲染一块毛玻璃面板（RGBA）。

    Args:
        width/height: 面板尺寸
        radius: 圆角半径
        top/bottom: 竖向渐变的两端颜色
        alpha: 面板主体不透明度 0-255
        accent: 强调色（描边光晕）
        glow: 是否绘制顶部高光与边缘光
        grain: 磨砂噪点强度（0 = 关闭）
        shadow: 外阴影半径（0 = 关闭）
    """
    width = max(8, int(width))
    height = max(8, int(height))
    top_rgb = hex_to_rgb(top or COLORS["card"])
    bottom_rgb = hex_to_rgb(bottom or COLORS["bg_alt"])
    accent_rgb = hex_to_rgb(accent or COLORS["accent"])

    pad = int(shadow) if shadow else 0
    canvas_size = (width + pad * 2, height + pad * 2)
    panel = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    grad = Image.new("RGBA", (width, height))
    gd = ImageDraw.Draw(grad)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = mix(top_rgb, bottom_rgb, ratio)
        gd.line([(0, y), (width, y)], fill=(color[0], color[1], color[2], alpha))

    if grain:
        noise = Image.effect_noise((width, height), 24).convert("L")
        noise = noise.point(lambda v: int(v * grain / 255))
        grad = Image.composite(
            Image.new("RGBA", (width, height), (255, 255, 255, 0)), grad, noise)

    panel.paste(grad, (pad, pad), _rounded_mask((width, height), radius))

    draw = ImageDraw.Draw(panel)
    box = [pad, pad, pad + width - 1, pad + height - 1]

    if glow:
        for i in range(3):
            alpha_edge = max(0, int(border_alpha * (1 - i / 3.0)))
            draw.rounded_rectangle(
                [box[0] + i, box[1] + i, box[2] - i, box[3] - i],
                radius=max(2, radius - i),
                outline=(accent_rgb[0], accent_rgb[1], accent_rgb[2], alpha_edge),
                width=1)
        draw.line([(pad + radius, pad + 1), (pad + width - radius, pad + 1)],
                  fill=(255, 255, 255, 46), width=1)

    if shadow:
        shadow_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.rounded_rectangle([pad, pad + 2, pad + width - 1, pad + height + 1],
                             radius=radius, fill=(0, 0, 0, 110))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow / 2))
        panel = Image.alpha_composite(shadow_layer, panel)

    return panel


# ════════════════════════════════════════════
# 相片卡（挂在绳子上的那张）
# ════════════════════════════════════════════

def photo_card(image, width: int = 148, height: int = 132, *, caption: str = "",
               accent: str = None, pinned: bool = False,
               radius: int = 6, clip: bool = True, shadow: int = 12):
    """
    渲染一张“相片卡”：白边相纸 + 顶部金属夹 + 底部标题，带透明阴影。

    Args:
        image: PIL.Image（截图内容）
        width/height: 卡片尺寸（不含阴影）
        caption: 底部标题
        accent: 强调色（收藏时夹子会发亮）
    """
    width = max(48, int(width))
    height = max(48, int(height))
    accent_rgb = hex_to_rgb(accent or COLORS["accent"])

    pad = max(4, int(shadow))
    cap_h = 18 if caption else 0
    photo_h = height - cap_h - 10

    card = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))

    if shadow:
        sh = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [pad, pad + 3, pad + width - 1, pad + height + 2],
            radius=radius + 2, fill=(0, 0, 0, 120))
        card = Image.alpha_composite(
            card, sh.filter(ImageFilter.GaussianBlur(max(1, shadow / 2.2))))

    paper = Image.new("RGBA", (width, height), (247, 249, 252, 255))
    pd = ImageDraw.Draw(paper)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = mix((252, 253, 255), (226, 232, 242), ratio)
        pd.line([(0, y), (width, y)], fill=(color[0], color[1], color[2], 255))
    card.paste(paper, (pad, pad), _rounded_mask((width, height), radius))

    if image is not None:
        box_w = max(8, width - 10)
        box_h = max(8, photo_h - 4)
        try:
            shot = image.convert("RGB")
            scale = max(box_w / shot.width, box_h / shot.height)
            new_size = (max(1, int(shot.width * scale)),
                        max(1, int(shot.height * scale)))
            shot = shot.resize(new_size, Image.LANCZOS)
            left = (shot.width - box_w) // 2
            top = (shot.height - box_h) // 2
            shot = shot.crop((left, top, left + box_w, top + box_h))
            card.paste(shot, (pad + 5, pad + 5))
        except Exception:
            pass

    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle(
        [pad, pad, pad + width - 1, pad + height - 1],
        radius=radius, outline=(148, 160, 180, 140), width=1)

    if cap_h:
        text = caption if len(caption) <= 12 else caption[:11] + "…"
        font = _font(11)
        if font:
            tw = draw.textlength(text, font=font)
            draw.text((pad + (width - tw) / 2, pad + height - cap_h + 2),
                      text, font=font, fill=(62, 72, 94, 255))

    if clip:
        clip_w, clip_h = 26, 12
        cx = pad + width // 2
        draw.rounded_rectangle(
            [cx - clip_w // 2, pad - 6, cx + clip_w // 2, pad + clip_h - 6],
            radius=4, fill=(96, 108, 130, 255),
            outline=(64, 74, 92, 255), width=1)
        ring = (accent_rgb[0], accent_rgb[1], accent_rgb[2], 255) if pinned \
            else (176, 186, 204, 255)
        draw.ellipse([cx - 8, pad - 12, cx + 8, pad + 4], outline=ring, width=2)

    return card


def rotate_card(card: Image.Image, angle: float) -> Image.Image:
    """旋转已渲染的卡片（摆动动画用）"""
    if abs(angle) < 0.05:
        return card
    return card.rotate(angle, resample=Image.BICUBIC, expand=True)


# ════════════════════════════════════════════
# 小部件
# ════════════════════════════════════════════

def badge(text: str, *, fg: str = None, accent: str = None,
          font_size: int = 11, pad_x: int = 10, pad_y: int = 4):
    """玻璃徽章（计数、提示）"""
    font = _font(font_size, True)
    fg_rgb = hex_to_rgb(fg or COLORS["text"])
    accent = accent or COLORS["accent"]

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw = probe.textlength(text, font=font) if font else len(text) * 7
    width = int(tw + pad_x * 2)
    height = int(font_size + pad_y * 2 + 4)

    img = glass_panel(width, height, radius=height // 2, alpha=190,
                      accent=accent, border_alpha=90, grain=0, shadow=6)
    draw = ImageDraw.Draw(img)
    off = (img.width - width) // 2
    if font:
        draw.text((off + pad_x, off + pad_y - 1), text, font=font,
                  fill=fg_rgb + (255,))
    return img


def strip_backdrop(width: int, height: int, *, tint: str = None,
                   accent: str = None, rope_y: int = 26, sag: int = 14,
                   alpha_top: int = 168, alpha_bottom: int = 235,
                   grain: int = 5):
    """
    绳子条带的背景：上浅下深的竖向渐变 + 绳线附近的强调光 + 磨砂噪点。

    贴在画布最底层，让整条绳子有厚度，而不是一块纯色板。
    """
    width = max(8, int(width))
    height = max(8, int(height))
    tint_rgb = hex_to_rgb(tint or COLORS["bg"])
    accent_rgb = hex_to_rgb(accent or COLORS["accent"])

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(1, height - 1)
        alpha = int(alpha_top + (alpha_bottom - alpha_top) * (ratio ** 1.35))
        color = mix(tint_rgb, (0, 0, 0), min(0.45, ratio * 0.55))
        draw.line([(0, y), (width, y)], fill=(color[0], color[1], color[2], alpha))

    # 绳线附近的柔光
    for i in range(14):
        offset = i * 3
        alpha = max(0, int(26 - i * 2))
        if alpha <= 0:
            continue
        draw.line([(0, rope_y + offset), (width, rope_y + offset)],
                  fill=(accent_rgb[0], accent_rgb[1], accent_rgb[2], alpha))

    if grain:
        noise = Image.effect_noise((width, height), 18).convert("L")
        noise = noise.point(lambda v: int(v * grain / 255))
        img = Image.composite(
            Image.new("RGBA", (width, height), (255, 255, 255, 0)), img, noise)
    return img


def glow_dot(size: int = 10, color: str = None):
    """发光小圆点（绳子端点 / 装饰）"""
    rgb = hex_to_rgb(color or COLORS["accent"])
    img = Image.new("RGBA", (size * 3, size * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size * 3 // 2
    for i, alpha in enumerate((40, 80, 150, 255)):
        r = size * (1.4 - i * 0.28)
        if r <= 0:
            continue
        d.ellipse([c - r, c - r, c + r, c + r], fill=rgb + (alpha,))
    return img


def rope_curve(width: int, sag: int = 16, y: int = 18, thickness: int = 3,
               color: str = None, highlight: str = None):
    """渲染一根下垂的绳（RGBA 贴图）"""
    rgb = hex_to_rgb(color or "#6E7C99")
    hi = hex_to_rgb(highlight or "#C6D2E6")
    img = Image.new("RGBA", (max(2, int(width)), int(y + sag + thickness * 3)),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    steps = max(24, int(width) // 6)
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = t * (width - 1)
        yy = y + sag * (1 - (2 * t - 1) ** 2)
        points.append((x, yy))
    for width_px, col, alpha in ((thickness + 2, (0, 0, 0), 90),
                                 (thickness, rgb, 255),
                                 (max(1, thickness - 2), hi, 150)):
        d.line(points, fill=col + (alpha,), width=width_px, joint="curve")
    return img


def ensure_rgba(image) -> Image.Image:
    """转成 RGBA"""
    return image if image.mode == "RGBA" else image.convert("RGBA")
