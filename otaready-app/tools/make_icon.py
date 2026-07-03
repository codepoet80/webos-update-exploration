#!/usr/bin/env python3
"""Generate the OTA Ready app icon in the webOS glossy-circle style.

Motif: broadcast dot + arcs (over-the-air) feeding a bold download arrow.
Drawn at 512px with supersampling, saved at 64px (launcher) and 48px (header).
"""
from PIL import Image, ImageDraw, ImageFilter

S = 512
CX = S // 2

def vertical_gradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        col = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        d.line([(0, y), (size, y)], fill=col)
    return img

# --- base: glossy slate-blue circle (webOS settings-app look) ---
icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# soft drop shadow
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).ellipse([30, 42, S - 30, S - 18], fill=(0, 0, 0, 110))
shadow = shadow.filter(ImageFilter.GaussianBlur(10))
icon.alpha_composite(shadow)

MARGIN = 34
circle_box = [MARGIN, MARGIN, S - MARGIN, S - MARGIN]

grad = vertical_gradient(S, (96, 112, 130), (28, 36, 46))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).ellipse(circle_box, fill=255)
icon.paste(grad, (0, 0), mask)

# dark rim
ImageDraw.Draw(icon).ellipse(circle_box, outline=(15, 20, 27, 255), width=6)
inner = [c + 6 if i < 2 else c - 6 for i, c in enumerate(circle_box)]
ImageDraw.Draw(icon).ellipse(inner, outline=(150, 165, 180, 90), width=3)

# --- glyph: transmitter dot + two broadcast arcs + download arrow ---
g = ImageDraw.Draw(icon)
WHITE = (250, 252, 255, 255)
GREEN = (130, 200, 40, 255)

dot_y = 178
g.ellipse([CX - 20, dot_y - 20, CX + 20, dot_y + 20], fill=WHITE)

for r in (52, 90):
    g.arc([CX - r, dot_y - r, CX + r, dot_y + r], start=205, end=335, fill=WHITE, width=17)

# arrow (green = "ready"): shaft + head
shaft_w, shaft_top, head_top, tip_y, head_half = 26, 226, 306, 388, 62
g.rectangle([CX - shaft_w, shaft_top, CX + shaft_w, head_top + 8], fill=GREEN)
g.polygon([(CX - head_half, head_top), (CX + head_half, head_top), (CX, tip_y)], fill=GREEN)
# landing line under the arrow
g.rounded_rectangle([CX - 78, 408, CX + 78, 430], radius=11, fill=WHITE)

# --- gloss: bright sheen on the upper half ---
gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(gloss)
gd.ellipse([MARGIN + 14, MARGIN + 6, S - MARGIN - 14, CX + 30], fill=(255, 255, 255, 70))
gloss_mask = Image.new("L", (S, S), 0)
gm = ImageDraw.Draw(gloss_mask)
gm.ellipse([MARGIN + 14, MARGIN + 6, S - MARGIN - 14, CX + 30], fill=255)
grad_a = Image.new("L", (S, S), 0)
ga = ImageDraw.Draw(grad_a)
for y in range(MARGIN, CX + 40):
    t = (y - MARGIN) / (CX + 40 - MARGIN)
    ga.line([(0, y), (S, y)], fill=int(90 * (1 - t)))
gloss.putalpha(Image.composite(grad_a, Image.new("L", (S, S), 0), gloss_mask))
icon.alpha_composite(gloss)

icon.resize((64, 64), Image.LANCZOS).save(
    "org.webosarchive.otaready/icon.png")
icon.resize((48, 48), Image.LANCZOS).save(
    "org.webosarchive.otaready/images/header-icon-otaready.png")
print("wrote icon.png (64), header-icon-otaready.png (48)")
