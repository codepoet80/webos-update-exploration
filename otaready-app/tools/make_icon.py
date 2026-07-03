#!/usr/bin/env python3
"""Generate the OTA Ready app icon in three sizes: 48, 64, 256.

Composition: a glossy dark webOS-style circle with the stock System Updates
*gift* (from updates.png) at the top, a bold green download arrow, and a white
landing slot at the bottom — the update being delivered to the device.

The circle / arrow / slot are drawn on a high-res master and downscaled per size;
the gift is composited at each output's NATIVE size. updates.png is only 64px, so
this keeps the gift as sharp as the source allows instead of upscaling a small
master. Run from anywhere: paths are resolved relative to this file.
"""
import os
from PIL import Image, ImageDraw, ImageFilter

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "org.webosarchive.otaready")
GIFT_SRC = os.path.join(APP, "updates.png")

GIFT_FRAC = 0.30    # gift width as a fraction of the icon
GIFT_CY = 0.235     # gift vertical centre as a fraction of the icon


def vgrad(size, top, bottom):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def render_base(S):
    """Glossy dark circle + green arrow + white slot (no gift), at resolution S."""
    f = S / 512.0
    def s(v):
        return int(round(v * f))
    CX = S // 2
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # soft drop shadow
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([s(30), s(42), S - s(30), S - s(18)], fill=(0, 0, 0, 110))
    icon.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s(10))))

    M = s(34)
    box = [M, M, S - M, S - M]
    grad = vgrad(S, (96, 108, 124), (26, 32, 40))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    icon.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(icon)
    d.ellipse(box, outline=(14, 18, 24, 255), width=s(6))
    d.ellipse([box[0] + s(6), box[1] + s(6), box[2] - s(6), box[3] - s(6)],
              outline=(150, 165, 180, 90), width=s(3))

    GREEN = (120, 196, 42, 255)
    WHITE = (248, 250, 253, 255)
    # green download arrow (sits below the gift)
    shaft_w, shaft_top, head_top, tip, head_half = s(24), s(250), s(322), s(398), s(60)
    d.rectangle([CX - shaft_w, shaft_top, CX + shaft_w, head_top + s(6)], fill=GREEN)
    d.polygon([(CX - head_half, head_top), (CX + head_half, head_top), (CX, tip)], fill=GREEN)
    # white landing slot
    d.rounded_rectangle([CX - s(78), s(410), CX + s(78), s(432)], radius=s(11), fill=WHITE)

    # gloss: white sheen fading downward, masked to the upper ellipse
    ga = Image.new("L", (S, S), 0)
    gad = ImageDraw.Draw(ga)
    for y in range(M, CX + s(40)):
        t = (y - M) / float(CX + s(40) - M)
        gad.line([(0, y), (S, y)], fill=int(85 * (1 - t)))
    gm = Image.new("L", (S, S), 0)
    ImageDraw.Draw(gm).ellipse([M + s(14), M + s(6), S - M - s(14), CX + s(30)], fill=255)
    sheen = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    sheen.putalpha(Image.composite(ga, Image.new("L", (S, S), 0), gm))
    icon.alpha_composite(sheen)
    return icon


def load_gift():
    """Isolate the colourful gift from updates.png, dropping its grey platform.

    Knock out low-saturation dark pixels (the platform / its shadow) to transparent,
    then crop to the bounding box of the remaining colourful gift pixels.
    """
    g = Image.open(GIFT_SRC).convert("RGBA")
    px = g.load()
    xs, ys = [], []
    for y in range(g.height):
        for x in range(g.width):
            r, gr, b, a = px[x, y]
            sat = max(r, gr, b) - min(r, gr, b)
            if a > 40 and sat < 28 and max(r, gr, b) < 170:
                px[x, y] = (r, gr, b, 0)          # grey platform -> transparent
            elif a > 60 and sat > 35 and max(r, gr, b) > 90:
                xs.append(x)                      # saturated gift pixel -> defines crop
                ys.append(y)
    if xs:
        g = g.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    return g


MASTER = render_base(2048)
GIFT = load_gift()


def compose(out):
    base = MASTER.resize((out, out), Image.LANCZOS)
    gw = max(1, int(round(out * GIFT_FRAC)))
    gh = max(1, int(round(gw * GIFT.height / float(GIFT.width))))
    gift = GIFT.resize((gw, gh), Image.LANCZOS)
    base.alpha_composite(gift, (out // 2 - gw // 2, int(round(out * GIFT_CY)) - gh // 2))
    return base


os.makedirs(os.path.join(APP, "images"), exist_ok=True)
compose(64).save(os.path.join(APP, "icon.png"))
compose(48).save(os.path.join(APP, "images", "header-icon-otaready.png"))
compose(256).save(os.path.join(APP, "icon-256x256.png"))
print("wrote icon.png (64), images/header-icon-otaready.png (48), icon-256x256.png (256)")
