"""App icons rendered from the square artwork in resources/icon.jpg.

Large icons show the whole character; small ones (tray, browser tab) zoom in on the face so they stay
recognizable. Without the artwork a simple fallback icon is drawn.
"""

import functools
import io

from PIL import Image, ImageDraw

from . import paths

# (minimum size, crop side as a fraction of the image) - the crop is centred slightly above the middle
ZOOM = ((64, 0.78), (32, 0.59), (0, 0.45))
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
FALLBACK_COLOR = (255, 138, 61, 255)


def _draw_fallback(size):
    """Rounded orange square with a white laptop, drawn at 4x and downsampled for smooth edges."""
    k = size * 4 / 64
    img = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 64 * k - 1, 64 * k - 1), radius=14 * k, fill=FALLBACK_COLOR)
    d.rounded_rectangle((14 * k, 17 * k, 50 * k, 40 * k), radius=3 * k, outline="white", width=round(4 * k))
    d.rounded_rectangle((9 * k, 45 * k, 55 * k, 49 * k), radius=2 * k, fill="white")
    return img.resize((size, size), Image.LANCZOS)


def render(size, rounded=True):
    """RGBA icon of size x size pixels."""
    if not paths.ICON_SOURCE.exists():
        return _draw_fallback(size)
    src = Image.open(paths.ICON_SOURCE).convert("RGB")
    frac = next(f for min_size, f in ZOOM if size >= min_size)
    side = min(src.size) * frac
    cx, cy = src.width * 0.5, src.height * 0.49
    left = min(max(0, cx - side / 2), src.width - side)
    top = min(max(0, cy - side / 2), src.height - side)
    # Downscale through a 4x intermediate and round the corners there for smooth edges
    big = src.crop((left, top, left + side, top + side)).resize((size * 4, size * 4), Image.LANCZOS).convert("RGBA")
    if rounded:
        mask = Image.new("L", big.size, 0)
        radius = big.width * (0.2 if size >= 32 else 0.16)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius=radius, fill=255)
        big.putalpha(mask)
    return big.resize((size, size), Image.LANCZOS)


def _png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def ico_bytes():
    """Multi-resolution .ico, each size rendered separately (not downscaled from 256)."""
    buf = io.BytesIO()
    images = [render(s) for s in ICO_SIZES]
    images[-1].save(buf, format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=images[:-1])
    return buf.getvalue()


def write_ico(path):
    path.write_bytes(ico_bytes())


WEB_ICONS = {
    "app-icon.png": ("image/png", lambda: _png(render(256))),
    # iOS rounds the corners itself and renders transparency as black
    "apple-touch-icon.png": ("image/png", lambda: _png(render(180, rounded=False).convert("RGB"))),
    "favicon.ico": ("image/x-icon", ico_bytes),
}


@functools.cache
def web_icon(name):
    """(content type, bytes) of an icon served to browsers, or None for an unknown name."""
    if name not in WEB_ICONS:
        return None
    content_type, build = WEB_ICONS[name]
    return content_type, build()


def window_icon_path():
    """An .ico file for the dashboard window when running from source (the .exe embeds its own)."""
    path = paths.CACHE_DIR / "app.ico"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_ico(path)
    return path
