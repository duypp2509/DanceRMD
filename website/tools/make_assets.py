"""Generate the website's image assets from the DanceRMD mascot artwork.

Usage (from the repository root):

    python website/tools/make_assets.py

Outputs go to ``website/assets/``: rounded logos, favicons, the Apple touch icon
and the 1200x630 Open Graph card. Re-run it whenever the artwork changes.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "dancermd" / "resources" / "icon.jpg"
OUT = ROOT / "website" / "assets"

BG = (12, 9, 7)
TEXT = (246, 239, 233)
MUTED = (168, 153, 140)
GRADIENT = ((255, 90, 31), (255, 138, 61), (255, 178, 56))

# Crop factor per output size: large icons show the whole character, tiny ones
# zoom into the face so it stays recognisable (mirrors the desktop app's icons).
ZOOM = ((64, 0.78), (32, 0.59), (0, 0.45))
FONT_CANDIDATES = {
    "bold": ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"),
    "regular": ("segoeui.ttf", "arial.ttf"),
}


def _crop(src: Image.Image, size: int) -> Image.Image:
    frac = next(f for min_size, f in ZOOM if size >= min_size)
    side = min(src.size) * frac
    cx, cy = src.width * 0.5, src.height * 0.49
    left = min(max(0, cx - side / 2), src.width - side)
    top = min(max(0, cy - side / 2), src.height - side)
    return src.crop((left, top, left + side, top + side))


def render_icon(src: Image.Image, size: int, rounded: bool = True) -> Image.Image:
    """Square RGBA icon; rendered at 4x and downsampled for smooth edges."""
    big = _crop(src, size).resize((size * 4, size * 4), Image.LANCZOS).convert("RGBA")
    if rounded:
        mask = Image.new("L", big.size, 0)
        radius = big.width * (0.22 if size >= 32 else 0.18)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius=radius, fill=255)
        big.putalpha(mask)
    return big.resize((size, size), Image.LANCZOS)


def _font(kind: str, size: int) -> ImageFont.ImageFont:
    for name in FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _gradient(width: int, height: int) -> Image.Image:
    """Horizontal brand gradient (hot -> orange -> amber)."""
    stops = (0.0, 0.45, 1.0)
    row = Image.new("RGB", (width, 1))
    px = row.load()
    for x in range(width):
        t = x / max(1, width - 1)
        i = 0 if t <= stops[1] else 1
        local = (t - stops[i]) / (stops[i + 1] - stops[i])
        a, b = GRADIENT[i], GRADIENT[i + 1]
        px[x, 0] = tuple(round(a[c] + (b[c] - a[c]) * local) for c in range(3))
    return row.resize((width, height))


def make_og_card(src: Image.Image) -> Image.Image:
    w, h = 1200, 630
    card = Image.new("RGB", (w, h), BG)

    # Warm glow behind the logo, echoing the mascot's orange light.
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((40, 70, 560, 590), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    card = Image.composite(Image.new("RGB", (w, h), (255, 110, 40)), card, glow)

    # Faint "code rain" columns along the right edge, like the mascot's background.
    draw = ImageDraw.Draw(card)
    mono = _font("regular", 18)
    rng = random.Random(7)
    for col in range(6):
        x = 1050 + col * 24
        for row in range(rng.randint(8, 24)):
            fade = max(0.15, 1 - row / 26)
            color = tuple(round(c * fade) for c in (92, 56, 30))
            draw.text((x, 10 + row * 25), rng.choice("0123456789ABCDEF{}=;<>"), font=mono, fill=color)

    logo = render_icon(src, 300)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((96, 182, 396, 482), radius=66, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    card.paste(shadow, (0, 0), shadow)
    card.paste(logo, (90, 165), logo)

    title_font = _font("bold", 104)
    title = "DanceRMD"
    box = draw.textbbox((0, 0), title, font=title_font)
    tw, th = box[2] - box[0], box[3] - box[1]
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).text((-box[0], -box[1]), title, font=title_font, fill=255)
    card.paste(_gradient(tw, th), (450, 200), mask)

    draw.text((452, 340), "Your Windows PC,", font=_font("bold", 46), fill=TEXT)
    draw.text((452, 396), "at your fingertips.", font=_font("bold", 46), fill=TEXT)
    draw.text((454, 476), "Control your laptop from any phone browser.", font=_font("regular", 28), fill=MUTED)
    draw.text((454, 516), "GPU streaming  ·  No phone app  ·  Works anywhere", font=_font("regular", 24),
              fill=(255, 178, 56))
    return card


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    src = Image.open(SOURCE).convert("RGB")

    for size in (64, 128, 256):
        render_icon(src, size).save(OUT / f"logo-{size}.png", optimize=True)
    render_icon(src, 32).save(OUT / "favicon-32.png", optimize=True)
    ico_sizes = (16, 32, 48)
    images = [render_icon(src, s) for s in ico_sizes]
    images[-1].save(OUT / "favicon.ico", format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=images[:-1])
    # iOS rounds the corners itself, so the touch icon stays square.
    render_icon(src, 180, rounded=False).save(OUT / "apple-touch-icon.png", optimize=True)
    # Mascot portrait for the page (uncropped, square, compressed).
    src.resize((640, 640), Image.LANCZOS).save(OUT / "mascot-640.jpg", quality=84, optimize=True, progressive=True)
    make_og_card(src).save(OUT / "og-card.png", optimize=True)
    print(f"Assets written to {OUT}")


if __name__ == "__main__":
    main()
