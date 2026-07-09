"""Temporary storage for weekly plan cover previews (before user approval)."""

import base64
import json
from pathlib import Path

from config import PREVIEWS_FILE
from models import Draft

STATUSES = ("pending", "approved", "skipped")


def _path() -> Path:
    p = Path(PREVIEWS_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_previews() -> dict:
    path = _path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_previews(data: dict) -> None:
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def preview_to_dict(draft: Draft, plan_day: int, status: str = "pending") -> dict:
    return {
        "plan_day": plan_day,
        "status": status,
        "lang": draft.lang,
        "title": draft.title,
        "summary": draft.summary,
        "body": draft.body,
        "keywords": draft.keywords,
        "tags": draft.tags,
        "slug": draft.slug,
        "scheduled_at": draft.scheduled_at,
        "source_topic": draft.source_topic,
        "image_mime": draft.image_mime,
        "image_b64": base64.b64encode(draft.image_bytes).decode() if draft.image_bytes else "",
    }


def dict_to_draft(item: dict) -> Draft:
    image_b64 = item.get("image_b64") or ""
    return Draft(
        lang=item.get("lang", "uk"),
        title=item.get("title", ""),
        summary=item.get("summary", ""),
        body=item.get("body", ""),
        keywords=item.get("keywords") or [],
        tags=item.get("tags") or [],
        slug=item.get("slug", ""),
        scheduled_at=item.get("scheduled_at", ""),
        image_bytes=base64.b64decode(image_b64) if image_b64 else b"",
        image_mime=item.get("image_mime", "image/jpeg"),
        source_topic=item.get("source_topic", ""),
    )


def set_preview(plan_day: int, draft: Draft, status: str = "pending") -> None:
    data = load_previews()
    data[str(plan_day)] = preview_to_dict(draft, plan_day, status)
    save_previews(data)


def get_preview(plan_day: int) -> dict | None:
    return load_previews().get(str(plan_day))


def update_preview_status(plan_day: int, status: str) -> None:
    data = load_previews()
    key = str(plan_day)
    if key in data:
        data[key]["status"] = status
        save_previews(data)


def remove_preview(plan_day: int) -> None:
    data = load_previews()
    data.pop(str(plan_day), None)
    save_previews(data)


def clear_previews() -> None:
    save_previews({})
