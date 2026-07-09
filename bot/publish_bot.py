#!/usr/bin/env python3
"""
Telegram bot for publishing blog posts to okdev.win via Cloudflare Worker.

Commands:
  /post uk|en  — start a draft
  Send photo + caption OR text with fields (title, summary, keywords, tags, slug)
  /publish      — publish draft to site
  /schedule ISO — set scheduledAt (e.g. 2026-07-10T09:00:00+03:00)
  /cancel       — discard draft
"""

import base64
import io
import os
import re
from dataclasses import dataclass, field

import requests

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
except ImportError:
    raise SystemExit("Install: pip install python-telegram-bot requests python-dotenv")

from dotenv import load_dotenv

load_dotenv()

WORKER_URL = os.getenv("WORKER_URL", "").rstrip("/")
PUBLISH_SECRET = os.getenv("PUBLISH_SECRET", "")
ALLOWED_IDS = {int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()}


@dataclass
class Draft:
    lang: str = "uk"
    title: str = ""
    summary: str = ""
    body: str = ""
    keywords: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    slug: str = ""
    scheduled_at: str = ""
    image_bytes: bytes = b""
    image_mime: str = "image/jpeg"


def allowed(user_id: int) -> bool:
    return not ALLOWED_IDS or user_id in ALLOWED_IDS


def parse_fields(text: str) -> dict:
    fields = {}
    body_lines = []
    for line in text.split("\n"):
        m = re.match(r"^(title|summary|keywords|tags|slug|schedule):\s*(.+)$", line.strip(), re.I)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            if key == "keywords":
                fields["keywords"] = [k.strip() for k in val.split(",") if k.strip()]
            elif key == "tags":
                fields["tags"] = [t.strip() for t in val.split(",") if t.strip()]
            elif key == "schedule":
                fields["scheduled_at"] = val
            else:
                fields[key] = val
        else:
            body_lines.append(line)
    fields["body"] = "\n".join(body_lines).strip()
    return fields


def get_draft(context: ContextTypes.DEFAULT_TYPE) -> Draft:
    if "draft" not in context.user_data:
        context.user_data["draft"] = Draft()
    return context.user_data["draft"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    await update.message.reply_text(
        "Бот публікації блогу okdev.win\n\n"
        "/post uk — новий пост (UA)\n"
        "/post en — new post (EN)\n"
        "Надішли фото з підписом або текст з полями title/summary/keywords/tags/slug\n"
        "/publish — опублікувати\n"
        "/schedule 2026-07-10T09:00:00+03:00 — запланувати\n"
        "/cancel — скасувати"
    )


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    lang = (context.args[0] if context.args else "uk").lower()
    if lang not in ("uk", "en"):
        lang = "uk"
    context.user_data["draft"] = Draft(lang=lang)
    await update.message.reply_text(f"Чернетка ({lang}). Надішли фото+підпис або текст з полями.")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    context.user_data.pop("draft", None)
    await update.message.reply_text("Чернетку скасовано.")


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    draft = get_draft(context)
    if context.args:
        draft.scheduled_at = " ".join(context.args)
        await update.message.reply_text(f"Заплановано: {draft.scheduled_at}")
    else:
        await update.message.reply_text("Вкажи дату: /schedule 2026-07-10T09:00:00+03:00")


async def cmd_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    draft = get_draft(context)
    if not draft.title or not draft.body:
        await update.message.reply_text("Потрібні title і body. Надішли текст з полями.")
        return
    if not WORKER_URL or not PUBLISH_SECRET:
        await update.message.reply_text("WORKER_URL або PUBLISH_SECRET не налаштовані в .env")
        return

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

    res = requests.post(
        f"{WORKER_URL}/posts",
        json=payload,
        headers={"X-Publish-Secret": PUBLISH_SECRET, "Content-Type": "application/json"},
        timeout=30,
    )
    data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
    if res.ok and data.get("ok"):
        slug = data.get("slug", draft.slug)
        await update.message.reply_text(f"✅ Опубліковано!\nSlug: {slug}\nURL: /blog/{slug}/")
        context.user_data.pop("draft", None)
    else:
        await update.message.reply_text(f"❌ Помилка: {data.get('error', res.text)}")


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    draft = get_draft(context)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    draft.image_bytes = buf.getvalue()
    draft.image_mime = "image/jpeg"
    if update.message.caption:
        await apply_text(draft, update.message.caption)
        await update.message.reply_text(f"Фото + текст збережено. Title: {draft.title or '(не вказано)'}\n/publish — опублікувати")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    draft = get_draft(context)
    await apply_text(draft, update.message.text)
    await update.message.reply_text(
        f"Збережено.\nTitle: {draft.title or '—'}\nKeywords: {', '.join(draft.keywords) or '—'}\n/publish — опублікувати"
    )


async def apply_text(draft: Draft, text: str):
    parsed = parse_fields(text)
    if parsed.get("title"):
        draft.title = parsed["title"]
    if parsed.get("summary"):
        draft.summary = parsed["summary"]
    if parsed.get("body"):
        draft.body = parsed["body"]
    if parsed.get("keywords"):
        draft.keywords = parsed["keywords"]
    if parsed.get("tags"):
        draft.tags = parsed["tags"]
    if parsed.get("slug"):
        draft.slug = parsed["slug"]
    if parsed.get("scheduled_at"):
        draft.scheduled_at = parsed["scheduled_at"]


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("publish", cmd_publish))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Blog publish bot running…")
    app.run_polling()


if __name__ == "__main__":
    main()
