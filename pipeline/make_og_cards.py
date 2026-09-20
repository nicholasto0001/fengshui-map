"""One Open Graph card per score, in the brand's own red and gold.

A link dropped into WhatsApp is judged on the preview alone, and every share
used to produce the same generic card — a 大吉 flat and a 差 one were
indistinguishable at the one moment the share has to do work.

The building's name and district go in og:title and og:description, which the
Worker rewrites per URL. What the picture carries is the score and the verdict,
and since the displayed score is a whole number between 21 and 89 that is 69
cards plus one for non-residential, all static.

On the design: the brand is deep red and gold, but the score has its own
meaning-bearing colour — red for 差 through teal for 大吉 — and a dark red disc
on a red card is invisible. So the card is a red envelope with an ivory label
inside it: the frame, the mark and the wordmark carry the brand, the label
carries the score at full contrast.

Burning the building's name into the image would mean rasterising Chinese text
at the edge on every request, which needs a font and a renderer in the Worker;
the name sits in the bold title line directly under the image instead.

Source: brand/logo-square.jpg
Output: og.png (the default card), og/s21.png … og/s89.png, og/nonres.png
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent.parent
SRC = ROOT / "brand" / "logo-square.jpg"
OUT = ROOT / "og"

W, H = 1200, 630

# Measured off the artwork itself, so the pasted mark sits on exactly its own
# red and the seam does not show.
RED = (167, 22, 30)
RED_DEEP = (134, 16, 23)
GOLD = (225, 179, 112)
GOLD_HI = (255, 226, 148)
IVORY = (250, 249, 246)
INK = (11, 11, 11)
INK2 = (85, 83, 78)
INK3 = (134, 132, 125)

MARK = (736, 175, 1266, 705)      # the pin, without the wordmark

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
f_tag = ImageFont.truetype(LIGHT, 23)
f_score = ImageFont.truetype(BOLD, 96)
f_verdict = ImageFont.truetype(BOLD, 66)
f_sub = ImageFont.truetype(LIGHT, 30)
f_unit = ImageFont.truetype(LIGHT, 31)
f_cta = ImageFont.truetype(BOLD, 33)
f_foot = ImageFont.truetype(LIGHT, 24)
f_small = ImageFont.truetype(LIGHT, 21)
f_big = ImageFont.truetype(BOLD, 44)


def percentiles() -> dict[int, int]:
    """How many of Hong Kong's homes each score beats.

    The three component bars cannot go on a card: the cards are cut by total
    score, and 2,015 buildings share a score of 54 with 環境 running from 46
    to 64 between them — a drawn bar would be wrong for most of them. This is
    derived from the total alone, so it is right for every building that lands
    on the card.
    """
    import bisect
    f = ROOT / "data" / "scores.json"
    if not f.exists():
        return {}
    import json
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    from build_tiles import is_dwelling, keep
    tot = sorted(round(r["total"]) for r in json.loads(f.read_text())
                 if keep(r) and is_dwelling(r))
    n = len(tot)
    return {s: round(100 * bisect.bisect_left(tot, s) / n) for s in range(21, 90)}


def rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def band(score: int) -> int:
    for i, b in enumerate(BREAKS):
        if score < b:
            return i
    return len(BREAKS)


def mark(size: int) -> Image.Image:
    """The pin, cut to a disc with a gold ring.

    Pasted square, the crop shows its seam: the artwork's red is flat and the
    card's is a gradient, so a rectangle of slightly-wrong red appears around
    it. A disc has no straight edge to give that away, and the ring echoes the
    round version of the logo.
    """
    im = Image.open(SRC).convert("RGB").crop(MARK)
    side = max(im.size)
    pad = Image.new("RGB", (side, side), im.getpixel((4, 4)))
    pad.paste(im, ((side - im.width) // 2, (side - im.height) // 2))

    S = size * 4                       # render big, downsample once
    big = pad.resize((S, S), Image.LANCZOS).convert("RGBA")
    hole = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hole).ellipse([0, 0, S - 1, S - 1], fill=255)
    big.putalpha(hole)
    ring = ImageDraw.Draw(big)
    ring.ellipse([3, 3, S - 4, S - 4], outline=GOLD, width=max(4, S // 64))
    return big.resize((size, size), Image.LANCZOS)


def centred(d, box, text, font, fill):
    x0, y0, x1, y1 = box
    b = d.textbbox((0, 0), text, font=font)
    d.text((x0 + (x1 - x0 - (b[2] - b[0])) / 2 - b[0],
            y0 + (y1 - y0 - (b[3] - b[1])) / 2 - b[1]), text, font=font, fill=fill)


def card(score: int | None, badge: Image.Image, pct: dict) -> Image.Image:
    img = Image.new("RGB", (W, H), RED)
    d = ImageDraw.Draw(img)

    # A little depth top to bottom, the way the artwork has it.
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(RED[i] + (RED_DEEP[i] - RED[i]) * t) for i in range(3)))

    # The gold ring, echoing the round version of the logo.
    d.rounded_rectangle([18, 18, W - 19, H - 19], radius=22, outline=GOLD, width=3)
    d.rounded_rectangle([27, 27, W - 28, H - 28], radius=16, outline=GOLD, width=1)

    img.paste(badge, (56, 40), badge)
    d.text((176, 50), "香港風水地圖", font=f_brand, fill=GOLD_HI)
    d.text((178, 100), "三元九運　第九運 2024–2043", font=f_tag, fill=GOLD)

    # The ivory label. The score ramp only means anything at full contrast,
    # and a 差 card's dark red disc would vanish straight into the envelope.
    PX0, PY0, PX1, PY1 = 48, 156, W - 48, H - 76
    d.rounded_rectangle([PX0, PY0, PX1, PY1], radius=26, fill=IVORY)

    if score is None:
        fill, ink, label, sub = NONRES, (58, 56, 51), "非住宅", "唔係住宅樓宇"
    else:
        i = band(score)
        fill, ink, label, sub = rgb(RAMP[i]), INKS[i], LABELS[i], SUBS[i]

    CX, CY, R = 186, 282, 86
    d.ellipse([CX - R - 5, CY - R - 5, CX + R + 5, CY + R + 5], fill=(236, 234, 228))
    d.ellipse([CX - R, CY - R, CX + R, CY + R], fill=fill)
    centred(d, (CX - R, CY - R, CX + R, CY + R),
            "—" if score is None else str(score), f_score, ink)

    x = CX + R + 52
    d.text((x, 206), label, font=f_verdict, fill=INK)
    d.text((x + 4, 288), sub, font=f_sub, fill=INK2)
    if score is not None:
        d.text((x + 4, 330), f"{score} / 100 分", font=f_unit, fill=INK3)

    # The right half was empty. What belongs there is the thing the score
    # alone can honestly say: where it sits among every home in Hong Kong,
    # and what the five colours on the map mean.
    SX0, SX1 = 672, PX1 - 52
    d.text((SX0, 200), "全港分佈", font=f_small, fill=INK3)
    seg = (SX1 - SX0) / len(RAMP)
    for i, hexc in enumerate(RAMP):
        x0 = SX0 + i * seg
        d.rectangle([x0 + 2, 232, x0 + seg - 2, 262], fill=rgb(hexc))
        centred(d, (x0, 268, x0 + seg, 296), LABELS[i], f_small,
                INK if (score is not None and band(score) == i) else INK3)
    if score is not None:
        i = band(score)
        cx = SX0 + i * seg + seg / 2
        d.polygon([(cx - 9, 226), (cx + 9, 226), (cx, 212)], fill=INK)
        d.text((SX0, 318), f"贏全港 {pct.get(score, 0)}%", font=f_big, fill=INK)
        d.text((SX0 + 2, 372), "住宅樓宇", font=f_small, fill=INK3)

    d.line([(PX0 + 44, 412), (PX1 - 44, 412)], fill=(230, 228, 222), width=1)
    d.text((PX0 + 44, 438), "撳入嚟睇飛星盤、坐向同評分拆解", font=f_cta, fill=INK)
    d.text((PX0 + 44, 486), "山水方位 · 玄空飛星 · 政府公開數據 · 每日更新",
           font=f_foot, fill=INK3)

    d.text((PX0, H - 58), "hkfengshuimap.com", font=f_foot, fill=GOLD)
    return img


def save(img: Image.Image, path: pathlib.Path) -> int:
    # 128 colours shows no banding in the gradient or the gilding at this
    # size, and takes each card from 77 KB to 23 KB — 70 of them ship with
    # the repository.
    img.convert("P", palette=Image.ADAPTIVE, colors=128).save(path, optimize=True)
    return path.stat().st_size


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"):
        f.unlink()

    badge = mark(96)
    pct = percentiles()
    total = 0
    for s in range(21, 90):
        total += save(card(s, badge, pct), OUT / f"s{s}.png")
    total += save(card(None, badge, pct), OUT / "nonres.png")

    # The default card, for the home page and for links that name no building.
    default = card(None, badge, pct)
    d = ImageDraw.Draw(default)
    d.rounded_rectangle([48, 156, W - 48, H - 76], radius=26, fill=IVORY)
    d.text((92, 206), "全港 84,720 棟樓宇", font=f_verdict, fill=INK)
    d.text((96, 300), "每一棟都有九運風水評分同玄空飛星盤", font=f_sub, fill=INK2)
    d.line([(92, 412), (W - 92, 412)], fill=(230, 228, 222), width=1)
    d.text((92, 438), "撳入嚟睇下你屋企幾多分", font=f_cta, fill=INK)
    d.text((92, 486), "山水方位 · 玄空飛星 · 政府公開數據 · 每日更新",
           font=f_foot, fill=INK3)
    d.text((48, H - 58), "hkfengshuimap.com", font=f_foot, fill=GOLD)
    save(default, ROOT / "og.png")

    n = len(list(OUT.glob("*.png")))
    print(f"og.png + {n} cards -> {OUT}  ({total/1024:.0f} KB total, "
          f"{total/n/1024:.0f} KB each)")


if __name__ == "__main__":
    main()
