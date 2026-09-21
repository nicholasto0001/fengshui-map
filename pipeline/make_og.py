"""Render the Open Graph card.

A link dropped into a Facebook group lives or dies on this image — without one
the post renders as a bare URL and scrolls past. The card has to state what the
thing is and give a reason to tap, at thumbnail size.
"""
from PIL import Image, ImageDraw, ImageFont
import pathlib

W, H = 1200, 630
OUT = pathlib.Path("/Users/nicholasto/Desktop/Claude Code/Feng Shui App/og.png")

BG      = (250, 249, 246)
INK     = (11, 11, 11)
INK2    = (85, 83, 78)
INK3    = (134, 132, 125)
RAMP    = ["#a01f1f", "#d76f6f", "#e6e4de", "#4da79a", "#0f6354"]
BRAND   = (27, 79, 143)

BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"

f_title = ImageFont.truetype(BOLD, 82)
f_sub   = ImageFont.truetype(LIGHT, 34)
f_stat  = ImageFont.truetype(BOLD, 46)
f_lab   = ImageFont.truetype(LIGHT, 25)
f_pill  = ImageFont.truetype(BOLD, 30)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# A soft map-ish ground: the diverging ramp as a band across the top edge.
for i, hexc in enumerate(RAMP):
    c = tuple(int(hexc[j:j+2], 16) for j in (1, 3, 5))
    d.rectangle([i * W // len(RAMP), 0, (i + 1) * W // len(RAMP), 14], fill=c)

PAD = 80
y = 96

d.text((PAD, y), "香港風水地圖", font=f_title, fill=INK)
y += 108
d.text((PAD, y), "睇樓、睇風水、睇你八字 — 搵個啱你住嘅地方", font=f_sub, fill=INK2)
y += 86

# 卡上面嗰句要講返我哋同人唔同嗰樣 —— 分數邊個睇都一樣，啱唔啱你先係
# 得你一個人有。所以問句係「啱你八字」，唔係「幾多分」。
d.rounded_rectangle([PAD, y, PAD + 530, y + 66], radius=33, fill=(238, 244, 251),
                    outline=(214, 228, 244), width=2)
d.text((PAD + 30, y + 16), "搵樓 ＋ 風水 ＋ 八字，三樣一齊", font=f_pill, fill=BRAND)
y += 118

stats = [("84,720", "幢逐幢計"), ("18", "區"), ("每日", "更新")]
x = PAD
for value, label in stats:
    d.text((x, y), value, font=f_stat, fill=INK)
    bbox = d.textbbox((x, y), value, font=f_stat)
    d.text((bbox[2] + 12, y + 16), label, font=f_lab, fill=INK3)
    x = d.textbbox((x, y), value, font=f_stat)[2] + 12 + \
        d.textbbox((0, 0), label, font=f_lab)[2] + 60

d.text((PAD, H - 88), "四柱八字 · 八宅 · 玄空飛星 · 政府公開數據", font=f_lab, fill=INK3)

# Score chips on the right, showing the colour language the map uses.
cx, cy = W - 300, 150
for i, (hexc, txt) in enumerate(zip(RAMP[::-1], ["大吉", "吉", "平穩", "欠佳", "差"])):
    c = tuple(int(hexc[j:j+2], 16) for j in (1, 3, 5))
    ink = (255, 255, 255) if i != 2 else (58, 56, 51)
    top = cy + i * 78
    d.rounded_rectangle([cx, top, cx + 210, top + 62], radius=31, fill=c)
    tb = d.textbbox((0, 0), txt, font=f_pill)
    d.text((cx + 105 - tb[2] // 2, top + 14), txt, font=f_pill, fill=ink)

img.save(OUT, "PNG", optimize=True)
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
