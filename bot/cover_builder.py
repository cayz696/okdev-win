"""Branded blog covers — Pillow only, zero AI text risk."""

from __future__ import annotations

import hashlib
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from models import Draft

BRAND_LOGO = Path(__file__).resolve().parent / "brand" / "okdev-logo.png"

# ok.dev palette (assets/style.css)
INK = (11, 14, 17)
SURFACE = (18, 22, 27)
WIRE = (45, 212, 191)
CYAN = (6, 182, 212)
SIGNAL = (245, 166, 35)
VIOLET = (167, 139, 250)

SIZE = (1280, 720)


def _rng(draft: Draft) -> random.Random:
    key = draft.slug or draft.title or "okdev"
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _vertical_gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = _lerp(INK[0], SURFACE[0], t)
        g = _lerp(INK[1], SURFACE[1], t)
        b = _lerp(INK[2], SURFACE[2], t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return img


def _glow_blob(
    size: tuple[int, int],
    center: tuple[float, float],
    radius: float,
    color: tuple[int, int, int],
    alpha: int,
) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    steps = 28
    for i in range(steps, 0, -1):
        t = i / steps
        r = radius * t
        a = int(alpha * (1 - t) ** 1.6)
        draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            fill=(*color, a),
        )
    return layer.filter(ImageFilter.GaussianBlur(radius=18))


def _wire_grid(size: tuple[int, int], alpha: int = 22) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    step = 64
    color = (*WIRE, alpha)
    for x in range(0, w + step, step):
        draw.line((x, 0, x, h), fill=color, width=1)
    for y in range(0, h + step, step):
        draw.line((0, y, w, y), fill=color, width=1)
    return layer


def _accent_arcs(size: tuple[int, int], rng: random.Random) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    palette = [WIRE, CYAN, VIOLET]
    for _ in range(rng.randint(2, 4)):
        color = palette[rng.randint(0, len(palette) - 1)]
        cx = rng.uniform(-w * 0.1, w * 1.1)
        cy = rng.uniform(h * 0.1, h * 0.9)
        r = rng.uniform(120, 320)
        start = rng.randint(0, 180)
        end = start + rng.randint(40, 120)
        draw.arc(
            (cx - r, cy - r, cx + r, cy + r),
            start=start,
            end=end,
            fill=(*color, rng.randint(35, 70)),
            width=rng.randint(2, 4),
        )
    return layer.filter(ImageFilter.GaussianBlur(radius=1.2))


def _signal_dot(size: tuple[int, int], rng: random.Random) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x = rng.uniform(w * 0.55, w * 0.88)
    y = rng.uniform(h * 0.12, h * 0.42)
    r = rng.uniform(4, 7)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=(*SIGNAL, 220))
    glow = _glow_blob(size, (x, y), r * 6, SIGNAL, 50)
    layer = Image.alpha_composite(layer, glow)
    return layer


def paste_logo(base: Image.Image) -> Image.Image:
    if not BRAND_LOGO.exists():
        return base
    logo = Image.open(BRAND_LOGO).convert("RGBA")
    target_h = int(base.height * 0.11)
    scale = target_h / logo.height
    target_w = int(logo.width * scale)
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    margin = int(base.width * 0.05)
    pos = (margin, base.height - target_h - margin)
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    base.paste(logo, pos, logo)
    return base


def build_branded_cover(draft: Draft) -> tuple[bytes, str]:
    w, h = SIZE
    rng = _rng(draft)

    base = _vertical_gradient(w, h).convert("RGBA")

    blobs = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    blob_colors = [WIRE, CYAN, VIOLET]
    for _ in range(rng.randint(3, 5)):
        color = blob_colors[rng.randint(0, len(blob_colors) - 1)]
        cx = rng.uniform(w * 0.15, w * 0.95)
        cy = rng.uniform(h * 0.05, h * 0.85)
        radius = rng.uniform(140, 360)
        alpha = rng.randint(55, 95)
        blob = _glow_blob((w, h), (cx, cy), radius, color, alpha)
        blobs = Image.alpha_composite(blobs, blob)

    base = Image.alpha_composite(base, blobs)
    base = Image.alpha_composite(base, _wire_grid((w, h)))
    base = Image.alpha_composite(base, _accent_arcs((w, h), rng))
    base = Image.alpha_composite(base, _signal_dot((w, h), rng))

    # subtle vignette
    vignette = Image.new("L", (w, h), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse((-w * 0.15, -h * 0.2, w * 1.15, h * 1.2), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=80))
    vig_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vig_px = vig_layer.load()
    vig_data = vignette.load()
    for y in range(h):
        for x in range(w):
            a = int((255 - vig_data[x, y]) * 0.45)
            if a:
                vig_px[x, y] = (0, 0, 0, a)
    base = Image.alpha_composite(base, vig_layer)

    base = paste_logo(base)
    out = base.convert("RGB")

    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue(), "image/jpeg"


def finish_cover_from_bytes(raw: bytes) -> tuple[bytes, str]:
    """Resize AI background and overlay ok.dev logo — guarantees no fake text on cover."""
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img = img.resize(SIZE, Image.Resampling.LANCZOS)
    img = paste_logo(img).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue(), "image/jpeg"
