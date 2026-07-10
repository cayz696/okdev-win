"""Blog cover images — Gemini by default, optional Pillow for logo overlay."""

import base64
import logging
import re

import httpx

from config import COVER_MODE, OPENROUTER_API_KEY, OPENROUTER_IMAGE_MODEL, SITE_DOMAIN
from models import Draft

OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"
log = logging.getLogger("okdev-bot")

BRAND_STYLE = (
    "Dark near-black background (#0b0e11 to #12161b). "
    "Mint-teal (#2dd4bf) and cyan (#06b6d4) accent glow. "
    "Optional tiny warm amber (#f5a623) light speck. "
    "Minimal premium developer aesthetic. "
)

VISUAL_THEMES = {
    "ai": "abstract neural pathways, soft nodes and connecting lines",
    "bot": "abstract chat bubbles as geometric shapes without symbols inside",
    "telegram": "abstract paper-plane geometry, messaging flow lines",
    "automation": "abstract gears and flowing pipelines, no labels",
    "business": "abstract growth curves and workflow arrows, no charts with text",
    "crm": "abstract connected dots network, CRM metaphor",
    "default": "abstract automation and technology atmosphere",
}


class ImageError(Exception):
    pass


def _headers() -> dict:
    if not OPENROUTER_API_KEY:
        raise ImageError("OPENROUTER_API_KEY не налаштований у .env")
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_DOMAIN,
        "X-Title": "okdev.win blog bot",
    }


def _visual_theme(draft: Draft) -> str:
    hay = " ".join(
        [draft.source_topic or "", draft.summary or "", " ".join(draft.tags or []), " ".join(draft.keywords or [])]
    ).lower()
    for key, theme in VISUAL_THEMES.items():
        if key != "default" and key in hay:
            return theme
    if re.search(r"\bai\b|агент|штучн", hay):
        return VISUAL_THEMES["ai"]
    if re.search(r"бот|telegram|телеграм", hay):
        return VISUAL_THEMES["telegram"]
    if re.search(r"автомат|рутин|бізнес|business", hay):
        return VISUAL_THEMES["automation"]
    return VISUAL_THEMES["default"]


def build_image_prompt(draft: Draft) -> str:
    theme = _visual_theme(draft)
    return (
        "Create ONE abstract blog hero background wallpaper. "
        f"Visual theme: {theme}. "
        f"{BRAND_STYLE} "
        "Soft cinematic lighting, depth, clean negative space. "
        "CRITICAL: the image must contain ZERO text — no letters, no words, no numbers, "
        "no typography, no captions, no headlines, no UI, no screenshots, no dashboards, "
        "no browser windows, no fake interfaces, no watermarks, no logos. "
        "Pure abstract illustration only."
    )


async def generate_cover_image(draft: Draft) -> tuple[bytes, str]:
    mode = COVER_MODE
    if mode == "brand":
        from cover_builder import build_branded_cover
        log.info("Cover: branded template for %s", draft.slug)
        return build_branded_cover(draft)
    if mode in ("gemini", "ai", "flux"):
        return await _generate_gemini_cover(draft)
    raise ImageError(f"Невідомий COVER_MODE={mode!r}. Використай gemini або brand.")


async def _generate_gemini_cover(draft: Draft) -> tuple[bytes, str]:
    prompt = build_image_prompt(draft)
    payload = {
        "model": OPENROUTER_IMAGE_MODEL,
        "prompt": prompt,
        "aspect_ratio": "16:9",
        "resolution": "1K",
        "output_format": "jpeg",
        "output_compression": 88,
        "n": 1,
    }

    log.info("Cover: %s via %s", draft.slug, OPENROUTER_IMAGE_MODEL)

    async with httpx.AsyncClient(timeout=180) as client:
        res = await client.post(OPENROUTER_IMAGE_URL, headers=_headers(), json=payload)

    if not res.is_success:
        raise ImageError(f"OpenRouter Image {res.status_code}: {res.text[:300]}")

    data = res.json()
    images = data.get("data") or []
    if not images:
        raise ImageError("OpenRouter не повернув зображення")

    b64 = images[0].get("b64_json")
    if not b64:
        raise ImageError("Порожня відповідь зображення")

    cost = (data.get("usage") or {}).get("cost")
    if cost is not None:
        log.info("Cover cost ~$%.4f", cost)

    raw = base64.b64decode(b64)

    try:
        from cover_builder import finish_cover_from_bytes
        return finish_cover_from_bytes(raw)
    except ImportError:
        log.info("Pillow not installed — using raw Gemini cover")
        return raw, "image/jpeg"
