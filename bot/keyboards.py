from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 AI-пост", callback_data="act:ai"),
            InlineKeyboardButton("💡 Моя ідея", callback_data="act:idea"),
        ],
        [
            InlineKeyboardButton("📅 План на тиждень", callback_data="act:plan"),
            InlineKeyboardButton("📋 Чернетка", callback_data="act:draft"),
        ],
        [
            InlineKeyboardButton("📆 Авторозклад", callback_data="act:schedule"),
            InlineKeyboardButton("⚙️ Налаштування", callback_data="act:settings"),
        ],
        [InlineKeyboardButton("🗑 Пости на сайті", callback_data="act:posts")],
    ])


def kb_lang(back: str = "nav:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇦 Українська", callback_data="lang:uk"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data=back)],
    ])


def kb_plan_days(count: int = 7, day_marks: dict[int, str] | None = None) -> InlineKeyboardMarkup:
    icons = {
        "pending": "🖼 ",
        "approved": "✅ ",
        "skipped": "⏭ ",
        "published": "🌐 ",
    }
    day_marks = day_marks or {}
    rows = []
    row = []
    for i in range(1, count + 1):
        mark = icons.get(day_marks.get(i), "")
        row.append(InlineKeyboardButton(f"{mark}День {i}", callback_data=f"plan:{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🎨 Згенерувати обкладинки", callback_data="act:plan_auto")])
    rows.append([
        InlineKeyboardButton("🔄 Новий план", callback_data="act:plan_new"),
        InlineKeyboardButton("🗑 Видалити план", callback_data="act:plan_clear"),
    ])
    rows.append([InlineKeyboardButton("◀️ Меню", callback_data="nav:main")])
    return InlineKeyboardMarkup(rows)


def kb_plan_confirm_new() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Так, згенерувати новий", callback_data="act:plan_force")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="act:plan")],
    ])


def kb_draft_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Сайт + канал", callback_data="pub:all"),
            InlineKeyboardButton("🌐 Тільки сайт", callback_data="pub:site"),
        ],
        [InlineKeyboardButton("📢 Тільки канал", callback_data="pub:channel")],
        [
            InlineKeyboardButton("✏️ Редагувати", callback_data="draft:edit"),
            InlineKeyboardButton("🔄 Перегенерувати", callback_data="draft:regen"),
        ],
        [
            InlineKeyboardButton("📷 Додати фото", callback_data="draft:photo"),
            InlineKeyboardButton("🎨 AI обкладинка", callback_data="draft:gen_image"),
        ],
        [
            InlineKeyboardButton("🗓 Розклад", callback_data="draft:schedule"),
            InlineKeyboardButton("⏰ В автопублікацію", callback_data="draft:queue"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="nav:back"),
            InlineKeyboardButton("❌ Скасувати", callback_data="draft:cancel"),
        ],
    ])


def kb_settings(channel: str) -> InlineKeyboardMarkup:
    label = channel or "не налаштовано"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 Канал: {label[:28]}", callback_data="set:channel")],
        [InlineKeyboardButton("🗑 Видалити канал", callback_data="set:channel_clear")],
        [InlineKeyboardButton("◀️ Меню", callback_data="nav:main")],
    ])


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Меню", callback_data="nav:main")]])


def kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="draft:cancel")]])


def kb_posts_list(posts: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in posts[:15]:
        slug = p.get("slug") or p.get("id") or "?"
        title = (p.get("title") or slug)[:36]
        lang = p.get("lang", "uk")
        rows.append([
            InlineKeyboardButton(f"🗑 {title}", callback_data=f"del:{lang}:{slug}"),
        ])
    rows.append([InlineKeyboardButton("🔄 Оновити", callback_data="act:posts")])
    rows.append([InlineKeyboardButton("◀️ Меню", callback_data="nav:main")])
    return InlineKeyboardMarkup(rows)


def kb_schedule_list(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in items[:10]:
        title = (item.get("title") or "?")[:28]
        day = item.get("plan_day")
        prefix = f"D{day} " if day else ""
        rows.append([
            InlineKeyboardButton(
                f"❌ {prefix}{title}",
                callback_data=f"sched:cancel:{item['id']}",
            ),
        ])
    rows.append([InlineKeyboardButton("🔄 Оновити", callback_data="act:schedule")])
    rows.append([InlineKeyboardButton("◀️ Меню", callback_data="nav:main")])
    return InlineKeyboardMarkup(rows)


def kb_delete_confirm(lang: str, slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Так, видалити", callback_data=f"delok:{lang}:{slug}"),
            InlineKeyboardButton("❌ Ні", callback_data="act:posts"),
        ],
    ])


def kb_plan_preview(day: int, status: str = "pending") -> InlineKeyboardMarkup | None:
    if status == "approved":
        return InlineKeyboardMarkup([[InlineKeyboardButton("✅ В автопублікації", callback_data="nav:main")]])
    if status == "skipped":
        return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропущено", callback_data="nav:main")]])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"prev:ok:{day}"),
            InlineKeyboardButton("🔄 Renew", callback_data=f"prev:renew:{day}"),
        ],
        [InlineKeyboardButton("⏭ Skip", callback_data=f"prev:skip:{day}")],
    ])
