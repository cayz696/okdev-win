"""Persistent weekly content plan storage."""

import json
from datetime import datetime, timezone
from pathlib import Path

from config import PLAN_FILE


def _path() -> Path:
    p = Path(PLAN_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_plan() -> dict | None:
    path = _path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        posts = data.get("posts") if isinstance(data, dict) else None
        if isinstance(posts, list) and posts:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def save_plan(posts: list[dict]) -> dict:
    data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "posts": posts,
    }
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def get_posts() -> list[dict]:
    plan = load_plan()
    return plan.get("posts", []) if plan else []


def clear_plan() -> None:
    path = _path()
    if path.exists():
        path.unlink()


def plan_created_label() -> str:
    plan = load_plan()
    if not plan or not plan.get("created_at"):
        return ""
    try:
        dt = datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return ""
