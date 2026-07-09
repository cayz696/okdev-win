"""Publish draft to okdev.win Worker and Telegram channel."""

import base64
import html
import logging
import re
from dataclasses import dataclass

import httpx
from telegram import Bot
from telegram.constants import ParseMode

from config import PUBLISH_SECRET, SITE_DOMAIN, WORKER_URL
from models import Draft

log = logging.getLogger(__name__)

TG_MESSAGE_MAX = 4096
TG_CAPTION_MAX = 1024
_TAG_RE = re.compile(r"[^\w\u0400-\u04FF]+")


def _tag_hashtag(tag: str) -> str:
    return html.escape(f"#{_TAG_RE.sub('_', tag)}")


class PublishError(Exception):
    pass


@dataclass
class PublishResult:
    site_ok: bool = False
    channel_ok: bool = False
    site_url: str = ""
    site_slug: str = ""
    site_error: str = ""
    channel_error: str = ""
    site_image: bool = False

    @property
    def all_ok(self) -> bool:
        return self.site_ok and self.channel_ok

    @property
    def any_ok(self) -> bool:
        return self.site_ok or self.channel_ok

    def summary_html(self, targets: set[str]) -> str:
        lines = ["<b>📊 Статус публікації</b>\n"]
        if "site" in targets:
            if self.site_ok:
                img = " (+ фото)" if self.site_image else ""
                lines.append(f"🌐 Сайт: ✅ {self.site_url}{img}")
            else:
                lines.append(f"🌐 Сайт: ❌ {self.site_error or 'помилка'}")
        if "channel" in targets:
            if self.channel_ok:
                img = " (+ фото)" if self.site_image else ""
                lines.append(f"📢 Канал: ✅{img}")
            else:
                lines.append(f"📢 Канал: ❌ {self.channel_error or 'помилка'}")
        if self.any_ok and not self.all_ok and targets == {"site", "channel"}:
            lines.append("\n⚠️ Часткова публікація. Чернетка збережена — можеш повторити канал.")
        elif self.all_ok or (len(targets) == 1 and self.any_ok):
            lines.append("\n✅ Готово!")
        return "\n".join(lines)


async def publish_to_site(draft: Draft) -> dict:
    if not WORKER_URL or not PUBLISH_SECRET:
        raise PublishError("WORKER_URL або PUBLISH_SECRET не налаштовані")

    payload = {
        "lang": draft.lang,
        "title": draft.title,
        "summary": draft.summary or draft.body[:200],
        "body": draft.body,
        "keywords": draft.keywords,
        "tags": draft.tags,
        "slug": draft.slug,
    }
    if draft.scheduled_at:
        payload["scheduledAt"] = draft.scheduled_at
    if draft.image_bytes:
        b64 = base64.b64encode(draft.image_bytes).decode()
        payload["imageBase64"] = f"data:{draft.image_mime};base64,{b64}"
        payload["imageMime"] = draft.image_mime

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"{WORKER_URL}/posts",
            json=payload,
            headers={"X-Publish-Secret": PUBLISH_SECRET, "Content-Type": "application/json"},
        )

    try:
        data = res.json()
    except Exception:
        data = {}

    if not res.is_success or not data.get("ok") or not data.get("slug"):
        raise PublishError(data.get("error", "Worker не зберіг пост — перевір WORKER_URL і PUBLISH_SECRET"))
    return data


def _truncate_text(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    para = cut.rfind("\n\n")
    if para > limit * 0.6:
        return cut[:para].rstrip()
    sentence = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence > limit * 0.6:
        return cut[: sentence + 1].rstrip()
    return cut.rstrip() + "…"


def _channel_message(draft: Draft, *, with_photo: bool) -> str:
    """Full post text for Telegram, respecting one-message limits."""
    url = f"{SITE_DOMAIN.rstrip('/')}{draft.post_url()}"
    title = html.escape(draft.title or "")
    body = html.escape((draft.body or "").strip())
    link = f"\n\n🔗 <a href=\"{html.escape(url)}\">Читати на okdev.win</a>"

    tags = ""
    if draft.tags:
        tags = "\n\n" + " ".join(_tag_hashtag(t) for t in draft.tags[:5])

    header = f"<b>{title}</b>\n\n"
    max_len = TG_CAPTION_MAX if with_photo else TG_MESSAGE_MAX
    reserved = len(link) + len(tags) + 20
    body_limit = max(200, max_len - len(header) - reserved)
    body = _truncate_text(body, body_limit)

    return header + body + tags + link


async def publish_to_channel(bot: Bot, channel_id: str, draft: Draft) -> None:
    if not channel_id:
        raise PublishError("Telegram-канал не налаштовано. ⚙️ Налаштування → Вказати канал")

    has_image = bool(draft.image_bytes)
    text = _channel_message(draft, with_photo=has_image)

    if has_image:
        await bot.send_photo(
            chat_id=channel_id,
            photo=draft.image_bytes,
            caption=text,
            parse_mode=ParseMode.HTML,
        )
    else:
        await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )


async def publish_draft(
    bot: Bot,
    draft: Draft,
    *,
    to_site: bool = False,
    to_channel: bool = False,
    channel_id: str = "",
) -> PublishResult:
    result = PublishResult(site_image=bool(draft.image_bytes))
    targets = set()
    if to_site:
        targets.add("site")
    if to_channel:
        targets.add("channel")

    if to_site:
        try:
            data = await publish_to_site(draft)
            result.site_ok = True
            result.site_slug = data.get("slug", draft.slug)
            result.site_url = f"{SITE_DOMAIN.rstrip('/')}{draft.post_url()}"
            if data.get("imageId"):
                result.site_image = True
        except PublishError as exc:
            result.site_error = str(exc)
            log.warning("Site publish failed: %s", exc)

    if to_channel:
        try:
            await publish_to_channel(bot, channel_id, draft)
            result.channel_ok = True
        except (PublishError, Exception) as exc:
            result.channel_error = str(exc)
            log.warning("Channel publish failed: %s", exc)

    if not result.any_ok:
        raise PublishError(result.summary_html(targets))

    return result
