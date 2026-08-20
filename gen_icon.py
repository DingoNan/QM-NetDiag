# -*- coding: utf-8 -*-
"""生成网络自检工具图标：政务蓝圆角渐变 + 白色网络信号弧线（可重复执行）"""
import os
from PIL import Image, ImageDraw

SIZE = 1024
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT_DIR, exist_ok=True)

# 1. 渐变背景（政务蓝：顶部 #14487A -> 底部 #2471B8）
grad = Image.new("RGB", (SIZE, SIZE))
top, bot = (20, 74, 122), (36, 113, 184)
for y in range(SIZE):
    t = y / SIZE
    color = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    ImageDraw.Draw(grad).line([(0, y), (SIZE, y)], fill=color)

# 2. 圆角方形遮罩
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=190, fill=255)
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)

# 3. 白色网络信号弧线（三条同心弧，向上张开，Wi-Fi 风格）
d = ImageDraw.Draw(img)
white = (255, 255, 255, 255)
cx, cy = SIZE // 2, SIZE // 2 + 30
for radius, width in ((150, 48), (280, 48), (410, 48)):
    d.arc([cx - radius, cy - radius, cx + radius, cy + radius],
          start=-72, end=72, fill=white, width=width)

# 4. 中心节点 + 顶部连接节点
d.ellipse([cx - 78, cy - 78, cx + 78, cy + 78], fill=white)
d.ellipse([cx - 46, cy - 400, cx + 46, cy + 400 - 92], fill=(255, 255, 255, 235))

# 5. 保存 PNG 与多尺寸 ICO
png_path = os.path.join(OUT_DIR, "netdiag_icon.png")
ico_path = os.path.join(OUT_DIR, "netdiag_icon.ico")
img.save(png_path)
img.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
# 6. 界面用的小尺寸 PNG（tkinter PhotoImage 支持 PNG）
for size in (48, 32):
    small = img.resize((size, size), Image.LANCZOS)
    small.save(os.path.join(OUT_DIR, f"netdiag_icon_{size}.png"))
print("图标已生成:")
for f in sorted(os.listdir(OUT_DIR)):
    print("  ", os.path.join(OUT_DIR, f))
