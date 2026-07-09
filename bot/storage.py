import json
import os
from pathlib import Path

from config import DEFAULT_CHANNEL_ID, SETTINGS_FILE


def _path() -> Path:
    p = Path(SETTINGS_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_settings() -> dict:
    path = _path()
    if not path.exists():
        return {"channel_id": DEFAULT_CHANNEL_ID}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    if not data.get("channel_id") and DEFAULT_CHANNEL_ID:
        data["channel_id"] = DEFAULT_CHANNEL_ID
    return data


def save_settings(data: dict) -> None:
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_channel_id() -> str:
    return load_settings().get("channel_id", "") or DEFAULT_CHANNEL_ID


def set_channel_id(channel_id: str) -> None:
    data = load_settings()
    data["channel_id"] = channel_id.strip()
    save_settings(data)


def clear_channel_id() -> None:
    data = load_settings()
    data["channel_id"] = ""
    save_settings(data)
