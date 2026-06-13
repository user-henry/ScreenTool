"""生成 ScreenTool 图标"""
from PIL import Image, ImageDraw, ImageFont
import os

assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
os.makedirs(assets_dir, exist_ok=True)

img = Image.new('RGBA', (256, 256), (0, 120, 212, 255))
d = ImageDraw.Draw(img)

# 白色矩形（截图窗口）
d.rectangle([28, 56, 228, 200], fill=(255, 255, 255, 255), outline=(200, 200, 200, 255), width=3)

# 蓝色标题条
d.rectangle([28, 56, 228, 85], fill=(0, 90, 180, 255))

# 文字区域
d.rectangle([48, 100, 208, 128], fill=(230, 230, 230, 255), outline=(200, 200, 200, 255))
d.rectangle([48, 140, 190, 168], fill=(230, 230, 230, 255), outline=(200, 200, 200, 255))
d.rectangle([48, 180, 160, 188], fill=(230, 230, 230, 255), outline=(200, 200, 200, 255))

# 保存 ICO
ico_path = os.path.join(assets_dir, 'icon.ico')
img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f'Icon saved to {ico_path}')
