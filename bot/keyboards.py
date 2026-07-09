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
        [InlineKeyboardButton("⚙️ Налаштування", callback_data="act:settings")],
    ])


def kb_lang(back: str = "nav:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇦 Українська", callback_data="lang:uk"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data=back)],
    ])


def kb_plan_days(count: int = 7) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i in range(1, count + 1):
        row.append(InlineKeyboardButton(f"День {i}", callback_data=f"plan:{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("🔄 Новий план", callback_data="act:plan"),
        InlineKeyboardButton("◀️ Меню", callback_data="nav:main"),
    ])
    return InlineKeyboardMarkup(rows)


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
