"""Render one Open Graph card per score, so a shared building looks like itself.

A link dropped into WhatsApp is judged on the preview alone. Every share used
to produce the same generic card, so a 大吉 flat and a 差 one were
indistinguishable and neither said anything about the building being sent.

The building's name and district go in og:title and og:description, which the
Worker rewrites per URL. What the *picture* can carry is the score and the
verdict — and since the displayed score is a whole number between 21 and 89,
that is 69 cards plus one for non-residential, all static. Burning the name
into the image would mean rendering Chinese text at the edge on every request,
which needs a font and a rasteriser in the Worker; the name sits in the bold
title line directly under the image instead.

Output: og/s21.png … og/s89.png, og/nonres.png
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "og"

W, H = 1200, 630
BG = (250, 249, 246)
INK = (11, 11, 11)
INK2 = (85, 83, 78)
INK3 = (134, 132, 125)

# The page's own scale, kept in step with BREAKS/RAMP/LEVELS in index.html.
BREAKS = [41, 46, 52, 58]
RAMP = ["#a01f1f", "#d76f6f", "#e6e4de", "#4da79a", "#0f6354"]
LABELS = ["差", "欠佳", "平穩", "吉", "大吉"]
SUBS = ["全港最低約兩成", "低於全港中位", "接近全港中位",
        "高於全港中位", "全港最高約一成"]
INKS = [(255, 255, 255), (255, 255, 255), (58, 56, 51),
        (255, 255, 255), (255, 255, 255)]
NONRES = (199, 197, 189)

BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
LIGHT = "/System/Library/Fonts/STHeiti Light.ttc"

f_brand = ImageFont.truetype(BOLD, 40)
f_score = ImageFont.truetype(BOLD, 240)
f_unit = ImageFont.truetype(LIGHT, 44)
f_verdict = ImageFont.truetype(BOLD, 72)
f_sub = ImageFont.truetype(LIGHT, 36)
f_cta = ImageFont.truetype(BOLD, 40)
f_foot = ImageFont.truetype(LIGHT, 27)


def rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def band(score: int) -> int:
    for i, b in enumerate(BREAKS):
        if score < b:
            return i
    return len(BREAKS)


def card(score: int | None) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    if score is None:
        fill, ink, label, sub = NONRES, (58, 56, 51), "非住宅", "唔係住宅樓宇"
    else:
        i = band(score)
        fill, ink, label, sub = rgb(RAMP[i]), INKS[i], LABELS[i], SUBS[i]

    # The same ramp strip the default card carries, so the family reads as one.
    for i, hexc in enumerate(RAMP):
        d.rectangle([i * W // len(RAMP), 0, (i + 1) * W // len(RAMP), 14],
                    fill=rgb(hexc))

    PAD = 80
    d.text((PAD, 74), "香港風水地圖 · 九運", font=f_brand, fill=INK2)

    # The score block, sized and coloured exactly like the one in the app, so
    # the card and the page a reader lands on agree at a glance.
    BX, BY, BS = PAD, 168, 300
    d.rounded_rectangle([BX, BY, BX + BS, BY + BS], radius=40, fill=fill)
    txt = "—" if score is None else str(score)
    tb = d.textbbox((0, 0), txt, font=f_score)
    d.text((BX + (BS - (tb[2] - tb[0])) / 2 - tb[0],
            BY + (BS - (tb[3] - tb[1])) / 2 - tb[1]), txt, font=f_score, fill=ink)

    x = BX + BS + 56
    d.text((x, BY + 22), label, font=f_verdict, fill=INK)
    d.text((x, BY + 124), sub, font=f_sub, fill=INK2)
    if score is not None:
        d.text((x, BY + 196), f"{score} / 100 分", font=f_unit, fill=INK3)

    d.text((PAD, 520), "撳入嚟睇飛星盤、坐向同山水方位", font=f_cta, fill=INK)
    d.text((PAD, H - 62), "山水方位 · 玄空飛星 · 政府公開數據",
           font=f_foot, fill=INK3)
    return img


def save(img: Image.Image, path: pathlib.Path) -> int:
    # Flat colour on a flat ground: a 64-colour palette is indistinguishable
    # here and roughly a fifth of the bytes, which matters when 70 of these
    # ship with the site.
    img.convert("P", palette=Image.ADAPTIVE, colors=64).save(path, optimize=True)
    return path.stat().st_size


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"):
        f.unlink()

    total = 0
    for s in range(21, 90):
        total += save(card(s), OUT / f"s{s}.png")
    total += save(card(None), OUT / "nonres.png")

    n = len(list(OUT.glob("*.png")))
    print(f"{n} cards -> {OUT}  ({total/1024:.0f} KB total, "
          f"{total/n/1024:.0f} KB each)")


if __name__ == "__main__":
    main()
