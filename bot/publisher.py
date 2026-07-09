"""Publish draft to okdev.win Worker and Telegram channel."""

import base64
import logging
from dataclasses import dataclass, field

import httpx
from telegram import Bot
from telegram.constants import ParseMode

from config import PUBLISH_SECRET, SITE_DOMAIN, WORKER_URL
from models import Draft

log = logging.getLogger(__name__)


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


def _channel_caption(draft: Draft) -> str:
    url = f"{SITE_DOMAIN.rstrip('/')}{draft.post_url()}"
    tags = " ".join(f"#{t.replace(' ', '_')}" for t in draft.tags[:4])
    kw = ", ".join(draft.keywords[:5])
    return (
        f"<b>{draft.title}</b>\n\n"
        f"{draft.summary}\n\n"
        f"🔗 {url}\n"
        f"{tags}\n"
        f"<i>{kw}</i>"
    )


async def publish_to_channel(bot: Bot, channel_id: str, draft: Draft) -> None:
    if not channel_id:
        raise PublishError("Telegram-канал не налаштовано. ⚙️ Налаштування → Вказати канал")

    caption = _channel_caption(draft)
    if len(caption) > 1024:
        caption = caption[:1020] + "…"

    if draft.image_bytes:
        await bot.send_photo(
            chat_id=channel_id,
            photo=draft.image_bytes,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    else:
        await bot.send_message(
            chat_id=channel_id,
            text=caption,
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
