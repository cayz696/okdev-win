"""Persistent queue for scheduled auto-publishing."""

import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import SCHEDULE_FILE
from models import Draft

log = logging.getLogger("okdev-bot")


def _path() -> Path:
    p = Path(SCHEDULE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_queue() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_queue(items: list[dict]) -> None:
    _path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def draft_from_item(item: dict) -> Draft:
    image_b64 = item.get("image_b64") or ""
    image_bytes = base64.b64decode(image_b64) if image_b64 else b""
    return Draft(
        lang=item.get("lang", "uk"),
        title=item.get("title", ""),
        summary=item.get("summary", ""),
        body=item.get("body", ""),
        keywords=item.get("keywords") or [],
        tags=item.get("tags") or [],
        slug=item.get("slug", ""),
        scheduled_at="",
        image_bytes=image_bytes,
        image_mime=item.get("image_mime", "image/jpeg"),
        source_topic=item.get("source_topic", ""),
    )


def item_from_draft(
    draft: Draft,
    *,
    plan_day: int = 0,
    notify_user_id: int,
    to_site: bool = True,
    to_channel: bool = True,
) -> dict:
    if not draft.scheduled_at:
        raise ValueError("scheduled_at required")
    if not draft.image_bytes:
        raise ValueError("image required")

    return {
        "id": str(uuid.uuid4()),
        "status": "pending",
        "plan_day": plan_day,
        "scheduled_at": draft.scheduled_at,
        "to_site": to_site,
        "to_channel": to_channel,
        "notify_user_id": notify_user_id,
        "lang": draft.lang,
        "title": draft.title,
        "summary": draft.summary,
        "body": draft.body,
        "keywords": draft.keywords,
        "tags": draft.tags,
        "slug": draft.slug,
        "source_topic": draft.source_topic,
        "image_mime": draft.image_mime,
        "image_b64": base64.b64encode(draft.image_bytes).decode(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published_at": "",
        "error": "",
    }


def add_to_queue(draft: Draft, **kwargs) -> dict:
    items = load_queue()
    # Replace existing pending item for same plan day or slug
    for i, existing in enumerate(items):
        if existing.get("status") != "pending":
            continue
        if kwargs.get("plan_day") and existing.get("plan_day") == kwargs["plan_day"]:
            items.pop(i)
            break
        if existing.get("slug") == draft.slug:
            items.pop(i)
            break

    item = item_from_draft(draft, **kwargs)
    items.append(item)
    save_queue(items)
    return item


def remove_from_queue(item_id: str) -> bool:
    items = load_queue()
    new_items = [i for i in items if i.get("id") != item_id]
    if len(new_items) == len(items):
        return False
    save_queue(new_items)
    return True


def get_pending() -> list[dict]:
    return sorted(
        [i for i in load_queue() if i.get("status") == "pending"],
        key=lambda x: x.get("scheduled_at", ""),
    )


def get_due(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    due = []
    for item in get_pending():
        raw = item.get("scheduled_at", "")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt <= now.astimezone(dt.tzinfo):
                due.append(item)
        except ValueError:
            log.warning("Bad scheduled_at: %s", raw)
    return due


def update_item(item_id: str, **fields) -> None:
    items = load_queue()
    for item in items:
        if item.get("id") == item_id:
            item.update(fields)
            break
    save_queue(items)


def is_plan_day_queued(plan_day: int) -> bool:
    return any(
        i.get("plan_day") == plan_day and i.get("status") == "pending"
        for i in load_queue()
    )
