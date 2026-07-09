#!/usr/bin/env python3
"""okdev.win blog bot — inline UI, AI (OpenRouter), site + Telegram channel publishing."""

import asyncio
import io
import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai_client import AIError, generate_post, generate_weekly_plan
from config import ALLOWED_IDS, SCHEDULE_CHECK_SECONDS, TELEGRAM_BOT_TOKEN
from image_client import ImageError, generate_cover_image
from keyboards import (
    kb_back_main,
    kb_cancel,
    kb_delete_confirm,
    kb_draft_actions,
    kb_lang,
    kb_main,
    kb_plan_days,
    kb_posts_list,
    kb_schedule_list,
    kb_settings,
)
from models import Draft
from posts_admin import PostsAdminError, delete_site_post, list_site_posts, post_admin_url
from publisher import PublishError, publish_draft
from schedule_storage import add_to_queue, get_pending, is_plan_day_queued, remove_from_queue
from scheduler import process_due_posts
from storage import clear_channel_id, get_channel_id, set_channel_id

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("okdev-bot")


def allowed(user_id: int) -> bool:
    return not ALLOWED_IDS or user_id in ALLOWED_IDS


def get_draft(context: ContextTypes.DEFAULT_TYPE) -> Draft:
    if "draft" not in context.user_data:
        context.user_data["draft"] = Draft()
    return context.user_data["draft"]


def clear_draft(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("draft", None)
    context.user_data.pop("mode", None)


def push_screen(context: ContextTypes.DEFAULT_TYPE, screen: str) -> None:
    stack = context.user_data.setdefault("nav_stack", [])
    if not stack or stack[-1] != screen:
        stack.append(screen)


def pop_screen(context: ContextTypes.DEFAULT_TYPE) -> str:
    stack = context.user_data.get("nav_stack", [])
    if len(stack) > 1:
        stack.pop()
    return stack[-1] if stack else "main"


async def safe_answer(query, text=None, show_alert: bool = False) -> None:
    """Telegram callback must be answered within ~10s; ignore stale queries."""
    try:
        await query.answer(text=text, show_alert=show_alert)
    except BadRequest as exc:
        if "too old" in str(exc).lower() or "invalid" in str(exc).lower():
            log.debug("Stale callback query ignored: %s", exc)
        else:
            raise


async def reply_or_edit(
    update: Update,
    text: str,
    reply_markup=None,
    parse_mode=None,
    *,
    answer: bool = True,
):
    if update.callback_query:
        if answer:
            await safe_answer(update.callback_query)
        try:
            await update.callback_query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def show_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = get_pending()
    if not pending:
        await reply_or_edit(
            update,
            "📆 <b>Авторозклад</b>\n\nЧерга порожня.\n\n"
            "Згенеруй <b>📅 План на тиждень</b> → "
            "<b>🎨 Обкладинки + автопублікація</b>",
            reply_markup=kb_back_main(),
            parse_mode="HTML",
        )
        return
    lines = ["📆 <b>Авторозклад</b>\n", f"В черзі: <b>{len(pending)}</b> постів\n"]
    for item in pending[:10]:
        day = f"День {item['plan_day']} · " if item.get("plan_day") else ""
        when = item.get("scheduled_at", "")[:16].replace("T", " ")
        lines.append(f"• {day}{item.get('title', '?')[:40]}")
        lines.append(f"  🕐 {when}")
    lines.append("\n<i>Бот має працювати постійно (run.bat).</i>")
    await reply_or_edit(
        update,
        "\n".join(lines),
        reply_markup=kb_schedule_list(pending),
        parse_mode="HTML",
    )


def _queued_plan_days() -> set[int]:
    return {i.get("plan_day") for i in get_pending() if i.get("plan_day")}


async def auto_queue_weekly_plan(bot, chat_id: int, user_id: int, plan: list[dict]) -> None:
    await bot.send_message(chat_id, "🎨 Генерую обкладинки для 7 постів…")
    queued = 0
    for p in plan:
        draft = Draft.from_ai(p)
        day = p.get("day", 0)
        try:
            image_bytes, mime = await generate_cover_image(draft)
            draft.image_bytes = image_bytes
            draft.image_mime = mime
            add_to_queue(
                draft,
                plan_day=day,
                notify_user_id=user_id,
                to_site=True,
                to_channel=True,
            )
            queued += 1
            await bot.send_message(
                chat_id,
                f"✅ День {day}: <b>{draft.title[:60]}</b>\n🕐 {draft.scheduled_at[:16]}",
                parse_mode="HTML",
            )
        except (ImageError, ValueError) as exc:
            await bot.send_message(chat_id, f"❌ День {day}: {exc}")

    await bot.send_message(
        chat_id,
        f"📆 <b>Автопублікація активна</b>\n\n"
        f"В черзі: <b>{queued}/7</b> постів.\n"
        f"Кожного дня о 09:00 (за датою плану) — сайт + канал.\n"
        f"Ти отримаєш повідомлення після кожної публікації.",
        parse_mode="HTML",
        reply_markup=kb_back_main(),
    )


async def show_posts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        posts = await list_site_posts(limit=30)
        if not posts:
            await reply_or_edit(
                update,
                "📚 <b>Пости на сайті</b>\n\nПоки немає опублікованих постів.",
                reply_markup=kb_back_main(),
                parse_mode="HTML",
            )
            return
        lines = ["📚 <b>Пости на сайті</b>\n", "Обери пост для видалення:\n"]
        for p in posts[:15]:
            lang = p.get("lang", "uk")
            slug = p.get("slug", "")
            lines.append(f"• [{lang}] {p.get('title', slug)}")
        await reply_or_edit(
            update,
            "\n".join(lines),
            reply_markup=kb_posts_list(posts),
            parse_mode="HTML",
        )
    except PostsAdminError as exc:
        await reply_or_edit(update, f"❌ {exc}", reply_markup=kb_back_main())


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nav_stack"] = ["main"]
    context.user_data.pop("mode", None)
    await reply_or_edit(
        update,
        "🏠 <b>okdev.win — блог-бот</b>\n\n"
        "Обери дію кнопками нижче.\n"
        "AI пише пости → ти публікуєш на сайт і/або в канал.",
        reply_markup=kb_main(),
        parse_mode="HTML",
    )


async def show_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, *, answer: bool = True):
    draft = get_draft(context)
    if not draft.title and not draft.body:
        await reply_or_edit(update, "Чернетка порожня.", reply_markup=kb_main())
        return
    push_screen(context, "draft")
    await reply_or_edit(
        update,
        draft.preview_text() + "\n\n<b>Куди публікувати?</b>"
        + ("" if draft.image_bytes else "\n<i>💡 Можеш згенерувати обкладинку: 🎨 AI обкладинка</i>"),
        reply_markup=kb_draft_actions(),
        parse_mode="HTML",
        answer=answer,
    )


async def run_ai_generate(update: Update, context: ContextTypes.DEFAULT_TYPE, from_idea: bool = False):
    draft = get_draft(context)
    topic = draft.source_topic or context.user_data.get("pending_topic", "")
    if not topic:
        await reply_or_edit(update, "Немає теми. Почни спочатку.", reply_markup=kb_main())
        return

    await reply_or_edit(update, "⏳ AI генерує пост…", reply_markup=None, answer=bool(update.callback_query))
    try:
        post = await generate_post(draft.lang, topic, from_idea=from_idea)
        new = Draft.from_ai(post)
        new.image_bytes = draft.image_bytes
        new.image_mime = draft.image_mime
        context.user_data["draft"] = new
        await show_draft(update, context, answer=False)
    except AIError as exc:
        await reply_or_edit(
            update,
            f"❌ AI: {exc}",
            reply_markup=kb_draft_actions() if draft.title else kb_main(),
            answer=False,
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    clear_draft(context)
    await show_main_menu(update, context)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        await update.callback_query.answer("Доступ заборонено", show_alert=True)
        return

    q = update.callback_query
    data = q.data or ""
    action, _, value = data.partition(":")

    try:
        if action == "nav":
            if value == "main":
                await show_main_menu(update, context)
            elif value == "back":
                screen = pop_screen(context)
                if screen == "draft":
                    await show_draft(update, context)
                else:
                    await show_main_menu(update, context)

        elif action == "act":
            if value == "ai":
                push_screen(context, "lang")
                context.user_data["mode"] = "topic"
                context.user_data["from_idea"] = False
                await reply_or_edit(
                    update,
                    "📝 <b>AI-пост</b>\n\nОбери мову, потім надішли тему.",
                    reply_markup=kb_lang(),
                    parse_mode="HTML",
                )
            elif value == "idea":
                push_screen(context, "lang")
                context.user_data["mode"] = "idea"
                context.user_data["from_idea"] = True
                await reply_or_edit(
                    update,
                    "💡 <b>Моя ідея</b>\n\nОбери мову → надішли сыру ідею одним повідомленням.\n"
                    "AI розгорне її в готовий пост.",
                    reply_markup=kb_lang(),
                    parse_mode="HTML",
                )
            elif value == "plan":
                await safe_answer(q)
                await reply_or_edit(update, "⏳ Генерую план на 7 днів…", answer=False)
                posts = await generate_weekly_plan()
                context.user_data["content_plan"] = posts
                lines = ["📅 <b>Контент-план на тиждень</b>\n"]
                for p in posts:
                    lines.append(f"<b>День {p['day']}</b> [{p.get('lang','uk')}] {p.get('title','')}")
                lines.append(
                    "\n<b>Швидко:</b> 🎨 Обкладинки + автопублікація — все одразу.\n"
                    "<b>Вручну:</b> обери день → обкладинка → ⏰ В автопублікацію."
                )
                await reply_or_edit(
                    update,
                    "\n".join(lines),
                    reply_markup=kb_plan_days(queued_days=_queued_plan_days()),
                    parse_mode="HTML",
                    answer=False,
                )
            elif value == "plan_auto":
                await safe_answer(q)
                plan = context.user_data.get("content_plan", [])
                if len(plan) < 7:
                    await reply_or_edit(
                        update,
                        "Спочатку згенеруй план на 7 днів.",
                        reply_markup=kb_main(),
                        answer=False,
                    )
                    return
                chat_id = update.effective_chat.id
                user_id = update.effective_user.id
                asyncio.create_task(
                    auto_queue_weekly_plan(context.bot, chat_id, user_id, plan)
                )
                await reply_or_edit(
                    update,
                    "⏳ Запускаю автопублікацію…\nДивись повідомлення нижче 👇",
                    answer=False,
                )
            elif value == "draft":
                await show_draft(update, context)
            elif value == "settings":
                ch = get_channel_id() or "не налаштовано"
                await reply_or_edit(
                    update,
                    f"⚙️ <b>Налаштування</b>\n\n"
                    f"📢 Канал: <code>{ch}</code>\n"
                    f"🤖 Модель: OpenRouter Gemini 3.1 Flash Lite\n"
                    f"📝 Промпти: <code>bot/prompts.py</code>\n\n"
                    f"Додай бота адміном каналу з правом публікації.",
                    reply_markup=kb_settings(ch),
                    parse_mode="HTML",
                )
            elif value == "posts":
                await show_posts_menu(update, context)
            elif value == "schedule":
                await show_schedule_menu(update, context)

        elif action == "sched":
            if value.startswith("cancel:"):
                item_id = value.split(":", 1)[1]
                if remove_from_queue(item_id):
                    await reply_or_edit(update, "✅ Прибрано з черги.", answer=False)
                else:
                    await reply_or_edit(update, "Не знайдено в черзі.", answer=False)
                await show_schedule_menu(update, context)

        elif action == "del":
            lang, _, slug = value.partition(":")
            if not slug:
                await reply_or_edit(update, "Невірний slug", reply_markup=kb_back_main(), answer=False)
                return
            await reply_or_edit(
                update,
                f"🗑 <b>Видалити з сайту?</b>\n\n"
                f"Slug: <code>{slug}</code>\n"
                f"URL: {post_admin_url(slug, lang)}\n\n"
                f"З каналу видали вручну.",
                reply_markup=kb_delete_confirm(lang, slug),
                parse_mode="HTML",
                answer=False,
            )

        elif action == "delok":
            lang, _, slug = value.partition(":")
            if not slug:
                await reply_or_edit(update, "Невірний slug", reply_markup=kb_back_main(), answer=False)
                return
            await reply_or_edit(update, "⏳ Видаляю…", answer=False)
            try:
                data = await delete_site_post(slug)
                title = data.get("title") or slug
                await reply_or_edit(
                    update,
                    f"✅ Видалено з сайту:\n<b>{title}</b>\n\nЗ каналу — видали вручну.",
                    reply_markup=kb_back_main(),
                    parse_mode="HTML",
                    answer=False,
                )
            except PostsAdminError as exc:
                await reply_or_edit(update, f"❌ {exc}", reply_markup=kb_back_main(), answer=False)

        elif action == "lang":
            draft = get_draft(context)
            draft.lang = value if value in ("uk", "en") else "uk"
            context.user_data["draft"] = draft
            mode = context.user_data.get("mode", "topic")
            if mode == "idea":
                context.user_data["mode"] = "idea_text"
                await reply_or_edit(
                    update,
                    f"💡 Надішли свою ідею ({draft.lang}):",
                    reply_markup=kb_cancel(),
                )
            else:
                context.user_data["mode"] = "topic_text"
                await reply_or_edit(
                    update,
                    f"📝 Надішли тему поста ({draft.lang}):",
                    reply_markup=kb_cancel(),
                )

        elif action == "plan":
            day = int(value)
            plan = context.user_data.get("content_plan", [])
            post = next((p for p in plan if p.get("day") == day), None)
            if not post:
                await reply_or_edit(update, "День не знайдено. Згенеруй план ще раз.", reply_markup=kb_main(), answer=False)
                return
            context.user_data["draft"] = Draft.from_ai(post)
            context.user_data["plan_day"] = day
            await show_draft(update, context, answer=False)

        elif action == "pub":
            draft = get_draft(context)
            if not draft.title or not draft.body:
                await reply_or_edit(update, "Чернетка порожня", reply_markup=kb_draft_actions(), answer=False)
                return

            to_site = value in ("all", "site")
            to_channel = value in ("all", "channel")
            targets = set()
            if to_site:
                targets.add("site")
            if to_channel:
                targets.add("channel")

            await reply_or_edit(update, "⏳ Публікую…", reply_markup=None, answer=False)
            try:
                result = await publish_draft(
                    context.bot,
                    draft,
                    to_site=to_site,
                    to_channel=to_channel,
                    channel_id=get_channel_id(),
                )
                # Очищаємо чернетку лише якщо всі обрані цілі успішні
                success = (
                    (not to_site or result.site_ok) and
                    (not to_channel or result.channel_ok)
                )
                if success:
                    clear_draft(context)
                    markup = kb_main()
                else:
                    markup = kb_draft_actions()

                await reply_or_edit(
                    update,
                    result.summary_html(targets),
                    reply_markup=markup,
                    parse_mode="HTML",
                    answer=False,
                )
            except PublishError as exc:
                await reply_or_edit(
                    update,
                    str(exc),
                    reply_markup=kb_draft_actions(),
                    parse_mode="HTML",
                    answer=False,
                )

        elif action == "draft":
            if value == "cancel":
                clear_draft(context)
                await show_main_menu(update, context)
            elif value == "regen":
                await run_ai_generate(update, context, from_idea=context.user_data.get("from_idea", False))
            elif value == "edit":
                context.user_data["mode"] = "edit"
                await reply_or_edit(
                    update,
                    "✏️ Надішли текст з полями:\n"
                    "<code>title: ...\nsummary: ...\nkeywords: a, b\ntags: T1\nslug: url-slug\n\nТекст статті.</code>",
                    reply_markup=kb_cancel(),
                    parse_mode="HTML",
                )
            elif value == "photo":
                context.user_data["mode"] = "photo"
                await reply_or_edit(
                    update,
                    "📷 Надішли фото (можна з підписом — title/summary в caption):",
                    reply_markup=kb_cancel(),
                )
            elif value == "gen_image":
                draft = get_draft(context)
                if not draft.title:
                    await reply_or_edit(update, "Спочатку згенеруй пост.", reply_markup=kb_main(), answer=False)
                    return
                await safe_answer(q)
                await reply_or_edit(update, "🎨 Генерую обкладинку (~15 сек)…", answer=False)
                try:
                    image_bytes, mime = await generate_cover_image(draft)
                    draft.image_bytes = image_bytes
                    draft.image_mime = mime
                    context.user_data["draft"] = draft
                    await show_draft(update, context, answer=False)
                except ImageError as exc:
                    await reply_or_edit(
                        update,
                        f"❌ Обкладинка: {exc}",
                        reply_markup=kb_draft_actions(),
                        answer=False,
                    )
            elif value == "queue":
                draft = get_draft(context)
                if not draft.title or not draft.body:
                    await reply_or_edit(update, "Чернетка порожня", reply_markup=kb_draft_actions(), answer=False)
                    return
                if not draft.image_bytes:
                    await reply_or_edit(
                        update,
                        "Спочатку згенеруй 🎨 AI обкладинку або надішли 📷 фото.",
                        reply_markup=kb_draft_actions(),
                        answer=False,
                    )
                    return
                if not draft.scheduled_at:
                    await reply_or_edit(
                        update,
                        "Немає дати. Обери пост з <b>📅 Плану на тиждень</b> або вкажи 🗓 Розклад.",
                        reply_markup=kb_draft_actions(),
                        parse_mode="HTML",
                        answer=False,
                    )
                    return
                try:
                    plan_day = context.user_data.get("plan_day", 0)
                    add_to_queue(
                        draft,
                        plan_day=plan_day,
                        notify_user_id=update.effective_user.id,
                        to_site=True,
                        to_channel=True,
                    )
                    when = draft.scheduled_at[:16].replace("T", " ")
                    await reply_or_edit(
                        update,
                        f"⏰ <b>В автопублікації</b>\n\n"
                        f"<b>{draft.title}</b>\n"
                        f"🕐 {when}\n"
                        f"📢 Сайт + канал",
                        reply_markup=kb_back_main(),
                        parse_mode="HTML",
                        answer=False,
                    )
                    clear_draft(context)
                except ValueError as exc:
                    await reply_or_edit(update, f"❌ {exc}", reply_markup=kb_draft_actions(), answer=False)
            elif value == "schedule":
                context.user_data["mode"] = "schedule"
                await reply_or_edit(
                    update,
                    "🗓 Надішли дату:\n<code>2026-07-10T09:00:00+03:00</code>",
                    reply_markup=kb_cancel(),
                    parse_mode="HTML",
                )

        elif action == "set":
            if value == "channel":
                context.user_data["mode"] = "channel"
                await reply_or_edit(
                    update,
                    "📢 Надішли @username каналу або chat_id (-100…):\n"
                    "Бот має бути <b>адміном</b> каналу.",
                    reply_markup=kb_cancel(),
                    parse_mode="HTML",
                )
            elif value == "channel_clear":
                clear_channel_id()
                await reply_or_edit(update, "Канал видалено.", reply_markup=kb_settings(""))

    except (AIError, PublishError, ImageError, PostsAdminError) as exc:
        log.warning("User action error: %s", exc)
        await reply_or_edit(update, f"❌ {exc}", reply_markup=kb_back_main(), answer=False)
    except Exception as exc:
        log.exception("Callback error: %s", exc)
        await reply_or_edit(
            update,
            f"❌ Помилка: {exc}\n\nСпробуй ще раз або повернись у меню.",
            reply_markup=kb_back_main(),
            answer=False,
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    mode = context.user_data.get("mode")
    text = (update.message.text or "").strip()
    if not text:
        return

    try:
        if mode == "channel":
            set_channel_id(text)
            try:
                await context.bot.get_chat(text)
            except Exception:
                await update.message.reply_text(
                    "⚠️ Канал збережено, але перевір що бот — адмін.\n"
                    "Якщо @username — спробуй chat_id -100…",
                    reply_markup=kb_settings(text),
                )
                context.user_data.pop("mode", None)
                return
            context.user_data.pop("mode", None)
            await update.message.reply_text(
                f"✅ Канал збережено: <code>{text}</code>",
                reply_markup=kb_settings(text),
                parse_mode="HTML",
            )
            return

        if mode == "schedule":
            get_draft(context).scheduled_at = text
            context.user_data.pop("mode", None)
            await update.message.reply_text(f"🗓 Заплановано: {text}", reply_markup=kb_draft_actions())
            return

        if mode in ("topic_text", "idea_text"):
            draft = get_draft(context)
            draft.source_topic = text
            context.user_data["draft"] = draft
            context.user_data.pop("mode", None)
            await run_ai_generate(update, context, from_idea=(mode == "idea_text"))
            return

        if mode == "edit":
            draft = get_draft(context)
            parsed = _parse_fields(text)
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
            context.user_data.pop("mode", None)
            await show_draft(update, context)
            return

        await update.message.reply_text("Обери дію в меню 👇", reply_markup=kb_main())

    except (AIError, PublishError, ImageError, PostsAdminError) as exc:
        await update.message.reply_text(f"❌ {exc}", reply_markup=kb_back_main())
    except Exception as exc:
        log.exception("Text handler error")
        await update.message.reply_text(f"❌ {exc}", reply_markup=kb_back_main())


def _parse_fields(text: str) -> dict:
    import re
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


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id):
        return
    if context.user_data.get("mode") not in ("photo", None) and not get_draft(context).title:
        await update.message.reply_text("Спочатку створи пост або натисни 📷 в чернетці.", reply_markup=kb_main())
        return

    draft = get_draft(context)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    draft.image_bytes = buf.getvalue()
    draft.image_mime = "image/jpeg"
    if update.message.caption:
        parsed = _parse_fields(update.message.caption)
        if parsed.get("title"):
            draft.title = parsed["title"]
        if parsed.get("summary"):
            draft.summary = parsed["summary"]
        if parsed.get("body"):
            draft.body = parsed["body"]
    context.user_data.pop("mode", None)
    context.user_data["draft"] = draft
    await update.message.reply_text("📷 Фото додано.", reply_markup=kb_draft_actions())
    await show_draft(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Щось пішло не так. Спробуй ще раз або /start",
                reply_markup=kb_back_main(),
            )
        except Exception:
            pass


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN не налаштований у .env")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(
            process_due_posts,
            interval=SCHEDULE_CHECK_SECONDS,
            first=30,
            name="scheduled_posts",
        )
        log.info("Scheduler active, check every %ss", SCHEDULE_CHECK_SECONDS)
    else:
        log.warning("Job queue unavailable — install python-telegram-bot[job-queue]")

    log.info("okdev.win blog bot started (inline UI, async, scheduler)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
