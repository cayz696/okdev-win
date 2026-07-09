"""Background job: publish due scheduled posts."""

import logging
from datetime import datetime, timezone

from config import ALLOWED_IDS
from publisher import PublishError, publish_draft
from schedule_storage import draft_from_item, get_due, update_item
from storage import get_channel_id

log = logging.getLogger("okdev-bot")


def _notify_user_id() -> int | None:
    return next(iter(ALLOWED_IDS), None) if ALLOWED_IDS else None


async def process_due_posts(context) -> None:
    due = get_due()
    if not due:
        return

    bot = context.bot
    channel_id = get_channel_id()
    notify_id = _notify_user_id()

    for item in due:
        item_id = item["id"]
        title = item.get("title", "Пост")
        log.info("Auto-publishing scheduled post: %s", title)

        try:
            draft = draft_from_item(item)
            result = await publish_draft(
                bot,
                draft,
                to_site=item.get("to_site", True),
                to_channel=item.get("to_channel", True),
                channel_id=channel_id,
            )
            update_item(
                item_id,
                status="published",
                published_at=datetime.now(timezone.utc).isoformat(),
                error="",
            )
            msg = (
                f"✅ <b>Автопублікація</b>\n\n"
                f"<b>{title}</b>\n"
                f"{result.summary_html({'site', 'channel'})}"
            )
            if notify_id:
                await bot.send_message(notify_id, msg, parse_mode="HTML")
        except (PublishError, Exception) as exc:
            log.exception("Scheduled publish failed for %s", title)
            update_item(item_id, status="failed", error=str(exc)[:500])
            if notify_id:
                await bot.send_message(
                    notify_id,
                    f"❌ <b>Автопублікація не вдалась</b>\n\n<b>{title}</b>\n{exc}",
                    parse_mode="HTML",
                )
