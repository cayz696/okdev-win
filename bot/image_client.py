"""OpenRouter image generation for blog covers."""

import base64
import logging

import httpx

from config import OPENROUTER_API_KEY, OPENROUTER_IMAGE_MODEL, SITE_DOMAIN
from models import Draft

OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"
log = logging.getLogger("okdev-bot")


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


def build_image_prompt(draft: Draft) -> str:
    keywords = ", ".join(draft.keywords[:5]) if draft.keywords else draft.summary[:120]
    return (
        "Professional blog hero image for a technology and automation article. "
        f"Topic: {draft.title}. "
        f"Context: {draft.summary[:200]}. "
        f"Keywords: {keywords}. "
        "Style: modern dark tech aesthetic, subtle blue accents, clean composition, "
        "high quality, no text, no logos, no watermarks, no faces close-up. "
        "Suitable for website header and Telegram channel cover."
    )


async def generate_cover_image(draft: Draft) -> tuple[bytes, str]:
    payload = {
        "model": OPENROUTER_IMAGE_MODEL,
        "prompt": build_image_prompt(draft),
        "aspect_ratio": "16:9",
        "resolution": "1K",
        "output_format": "jpeg",
        "output_compression": 85,
        "n": 1,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(OPENROUTER_IMAGE_URL, headers=_headers(), json=payload)

    if not res.is_success:
        raise ImageError(f"OpenRouter Image {res.status_code}: {res.text[:300]}")

    data = res.json()
    images = data.get("data") or []
    if not images:
        raise ImageError("OpenRouter не повернув зображення")

    item = images[0]
    b64 = item.get("b64_json")
    if not b64:
        raise ImageError("Порожня відповідь зображення")

    mime = item.get("media_type") or "image/jpeg"
    if mime == "image/png":
        mime = "image/jpeg"

    cost = (data.get("usage") or {}).get("cost")
    if cost is not None:
        log.info("Image generated via %s, cost ~$%.4f", OPENROUTER_IMAGE_MODEL, cost)

    return base64.b64decode(b64), mime
