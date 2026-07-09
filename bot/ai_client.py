"""Async OpenRouter AI client."""

import json
import re
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


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if match:
        return json.loads(match.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise AIError("AI повернув невалідний JSON")


async def chat(system: str, user: str, max_tokens: int = 2500) -> str:
    async with httpx.AsyncClient(timeout=90) as client:
        res = await client.post(
            OPENROUTER_URL,
            headers=_headers(),
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
        )
    if not res.is_success:
        raise AIError(f"OpenRouter {res.status_code}: {res.text[:300]}")
    data = res.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIError(f"Неочікувана відповідь OpenRouter") from exc


async def generate_post(lang: str, topic: str, from_idea: bool = False) -> dict:
    system = POST_FROM_IDEA_UK if from_idea and lang == "uk" else (
        POST_FROM_IDEA_EN if from_idea else (
            POST_FROM_TOPIC_UK if lang == "uk" else POST_FROM_TOPIC_EN
        )
    )
    raw = await chat(system, f"Тема/ідея: {topic}")
    post = _extract_json(raw)
    for key in ("title", "summary", "body", "keywords", "tags", "slug"):
        if key not in post:
            raise AIError(f"AI не повернув поле: {key}")
    post["lang"] = lang
    post["source_topic"] = topic
    return post


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
    for i, post in enumerate(posts[:7]):
        post["day"] = i + 1
        if not post.get("date"):
            post["date"] = days[i]
        post["scheduledAt"] = f"{post['date']}T09:00:00+03:00"
    return posts[:7]
