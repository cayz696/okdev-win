# okdev.win Blog Bot

Telegram-бот з **інлайн-кнопками**, AI (OpenRouter / Gemini 3.1 Flash Lite), публікація на **сайт + канал**.

## Швидкий старт

| Платформа | Інструкція |
|-----------|------------|
| **Windows Server** | [`DEPLOY-WINDOWS.md`](DEPLOY-WINDOWS.md) |
| Linux VPS | `portfolio-bot.service.example` |

```powershell
# Windows
cd bot
.\install.ps1
# заповни .env
.\run.ps1
```

## Кнопки бота (без команд)

`/start` → головне меню:

| Кнопка | Дія |
|--------|-----|
| 📝 AI-пост | Мова → тема → AI → превʼю → публікація |
| 💡 Моя ідея | Мова → ідея → AI розгортає → превʼю |
| 📅 План на тиждень | AI генерує 7 днів → обери день |
| 📋 Чернетка | Перегляд поточної |
| ⚙️ Налаштування | Telegram-канал для постингу |

**Публікація:** ✅ Сайт+канал · 🌐 Сайт · 📢 Канал · 📷 Фото · ✏️ Редагувати · 🔄 Перегенерувати · ◀️ Назад · ❌ Скасувати

## Промпти AI

Редагуй **`prompts.py`**:

- `POST_FROM_TOPIC_*` — пост з теми
- `POST_FROM_IDEA_*` — з твоєї сирої ідеї (рекомендовано для щотижневого контенту)
- `WEEKLY_PLAN` — 7 днів, мікс UA/EN, різні SEO-ніші

**Рекомендований workflow:**
1. Понеділок: `📅 План на тиждень`
2. Щодня: обери день → перевір → `✅ Сайт + канал`
3. Або кидай ідеї через `💡 Моя ідея` коли є натхнення

## .env

```env
TELEGRAM_BOT_TOKEN=
WORKER_URL=https://portfolio-contact-form.cayz696.workers.dev
PUBLISH_SECRET=
ALLOWED_USER_IDS=
OPENROUTER_API_KEY=
TELEGRAM_CHANNEL_ID=@your_channel
OPENROUTER_MODEL=google/gemini-3.1-flash-lite
```

## Канал

1. Створи канал → додай бота **адміном** (право публікації)
2. В боті: ⚙️ → вкажи `@channel` або `-100…`

## Архітектура

```
publish_bot.py  — UI, кнопки, стани
ai_client.py    — async OpenRouter
publisher.py    — сайт (Worker) + канал (Telegram)
prompts.py      — промпти (редагуй!)
keyboards.py    — інлайн-кнопки
storage.py      — збереження channel_id
```
