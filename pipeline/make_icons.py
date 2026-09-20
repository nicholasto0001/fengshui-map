"""App icons, cut from the brand artwork in brand/.

The old icons were a teal square with 風 set in a system font — a placeholder.
These come from the real logo instead.

Two crops, not one, and the reason is size. The full lockup carries
「香港風水地圖」under the mark, which is six characters that turn to mush below
about 64px: at a favicon's 32px they are three grey smudges. So the tab icon
and the small sizes use the mark alone — house, bagua, 吉 pin — which still
reads as a shape at 16px, and only the home-screen sizes keep the wordmark.

Source: brand/logo-square.jpg (the rounded-tile version).
Output: favicon.ico, apple-touch-icon.png, icon-192.png, icon-512.png
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
SRC = ROOT / "brand" / "logo-square.jpg"

# Measured off the artwork. The tile is the rounded square; the mark is the
# pin on its own, with the wordmark left out.
TILE = (626, 148, 1386, 940)     # full lockup, square-ish
MARK = (736, 175, 1266, 705)     # pin only


def cut(box: tuple[int, int, int, int], size: int) -> Image.Image:
    im = Image.open(SRC).convert("RGB").crop(box)
    # Square it off by padding with the artwork's own red rather than
    # stretching, so the bagua stays a circle.
    side = max(im.size)
    bg = im.getpixel((4, 4))
    pad = Image.new("RGB", (side, side), bg)
    pad.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return pad.resize((size, size), Image.LANCZOS)


def main() -> None:
    # Home screen: the OS applies its own mask, so the lockup is safe here.
    for name, size in (("apple-touch-icon.png", 180),
                       ("icon-192.png", 192),
                       ("icon-512.png", 512)):
        cut(TILE, size).save(ROOT / name, optimize=True)
        print(f"{name:<22} {size}x{size}  (full lockup)")

    # Tab icon: mark only, and rendered at each size rather than downscaled
    # from one, which is what keeps 16px from turning to porridge.
    ico = ROOT / "favicon.ico"
    cut(MARK, 256).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print(f"{'favicon.ico':<22} 16/32/48/64   (mark only)")


if __name__ == "__main__":
    main()
