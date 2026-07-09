"""Async OpenRouter AI client."""

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, SITE_DOMAIN, BOT_TIMEZONE
from prompts import (
    POST_FROM_IDEA_EN,
    POST_FROM_IDEA_UK,
    POST_FROM_TOPIC_EN,
    POST_FROM_TOPIC_UK,
    WEEKLY_PLAN,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TZ = ZoneInfo(BOT_TIMEZONE)
log = logging.getLogger("okdev-bot")


class AIError(Exception):
    pass


def _headers() -> dict:
    if not OPENROUTER_API_KEY:
        raise AIError("OPENROUTER_API_KEY не налаштований у .env")
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_DOMAIN,
        "X-Title": "okdev.win blog bot",
    }


def _strip_code_fence(text: str) -> str:
    text = text.strip().lstrip("\ufeff")
    if "```" not in text:
        return text
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.I)
    return blocks[0].strip() if blocks else text


def _find_json_block(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _repair_json(text: str) -> str:
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text


def _extract_json(text: str) -> dict:
    text = _strip_code_fence(text)
    candidates = [text]
    block = _find_json_block(text)
    if block and block not in candidates:
        candidates.append(block)

    last_err = None
    for candidate in candidates:
        for variant in (candidate, _repair_json(candidate)):
            try:
                data = json.loads(variant)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError as exc:
                last_err = exc

    log.warning("AI JSON parse failed: %s", (text[:500] + "…") if len(text) > 500 else text)
    raise AIError("AI повернув невалідний JSON") from last_err


def _slugify(title: str) -> str:
    text = unicodedata.normalize("NFD", (title or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\u0400-\u04FF]+", "-", text)
    return text.strip("-")[:80] or "post"


def _normalize_post(post: dict, lang: str, topic: str) -> dict:
    keywords = post.get("keywords") or []
    tags = post.get("tags") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    title = str(post.get("title") or topic).strip()
    body = str(post.get("body") or "").strip()
    summary = str(post.get("summary") or "").strip() or body[:200]

    if not title or not body:
        raise AIError("AI не повернув title або body")

    slug = str(post.get("slug") or "").strip() or _slugify(title)

    return {
        "title": title[:200],
        "summary": summary[:400],
        "body": body[:10000],
        "keywords": keywords[:12],
        "tags": tags[:8],
        "slug": slug[:80],
        "lang": lang,
        "source_topic": topic,
    }


async def chat(system: str, user: str, max_tokens: int = 2500) -> str:
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(OPENROUTER_URL, headers=_headers(), json=payload)

    if not res.is_success:
        # Деякі моделі не підтримують response_format — повтор без нього
        if res.status_code == 400 and "response_format" in res.text:
            payload.pop("response_format", None)
            async with httpx.AsyncClient(timeout=90) as client:
                res = await client.post(OPENROUTER_URL, headers=_headers(), json=payload)
        if not res.is_success:
            raise AIError(f"OpenRouter {res.status_code}: {res.text[:300]}")

    data = res.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIError("Неочікувана відповідь OpenRouter") from exc


async def generate_post(lang: str, topic: str, from_idea: bool = False) -> dict:
    system = POST_FROM_IDEA_UK if from_idea and lang == "uk" else (
        POST_FROM_IDEA_EN if from_idea else (
            POST_FROM_TOPIC_UK if lang == "uk" else POST_FROM_TOPIC_EN
        )
    )
    raw = await chat(system, f"Тема/ідея: {topic}")
    post = _extract_json(raw)
    return _normalize_post(post, lang, topic)


async def generate_weekly_plan() -> list[dict]:
    today = datetime.now(TZ).date()
    days = [(today + timedelta(days=i + 1)).isoformat() for i in range(7)]
    user = (
        f"Дати по порядку: {', '.join(days)}. "
        "Сьогодні — планування на наступні 7 днів. Різні ніші та SEO-ключі."
    )
    raw = await chat(WEEKLY_PLAN, user, max_tokens=6000)
    data = _extract_json(raw)
    posts = data.get("posts", [])
    if len(posts) < 7:
        raise AIError(f"Очікувалось 7 постів, отримано {len(posts)}")
    normalized = []
    for i, post in enumerate(posts[:7]):
        lang = post.get("lang", "uk")
        if lang not in ("uk", "en"):
            lang = "uk"
        item = _normalize_post(post, lang, post.get("title", f"day-{i+1}"))
        item["day"] = i + 1
        item["date"] = post.get("date") or days[i]
        item["scheduledAt"] = f"{item['date']}T09:00:00+03:00"
        normalized.append(item)
    return normalized
