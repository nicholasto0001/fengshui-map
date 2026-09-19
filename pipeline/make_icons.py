"""App icons.

Without these the browser asks for /favicon.ico on every load and logs a 404,
and "add to home screen" — the closest this gets to being an app — falls back
to a screenshot of the page.
"""
from PIL import Image, ImageDraw, ImageFont
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
TEAL = (15, 99, 84)
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


def icon(size: int, radius_ratio: float = 0.5) -> Image.Image:
    # Render at 4x and downsample: keeps the glyph edge clean at 32px.
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s, s], radius=int(s * radius_ratio), fill=TEAL)
    f = ImageFont.truetype(FONT, int(s * 0.62))
    bb = d.textbbox((0, 0), "風", font=f)
    d.text(((s - bb[2] - bb[0]) / 2, (s - bb[3] - bb[1]) / 2 - s * 0.02),
           "風", font=f, fill=(255, 255, 255))
    return img.resize((size, size), Image.LANCZOS)


icon(180, 0.22).save(ROOT / "apple-touch-icon.png")          # iOS home screen
icon(512, 0.22).save(ROOT / "icon-512.png")
icon(192, 0.22).save(ROOT / "icon-192.png")
ico = icon(64)
ico.save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("wrote favicon.ico, apple-touch-icon.png, icon-192.png, icon-512.png")
