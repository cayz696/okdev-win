# Деплой бота на Windows Server (без Docker)

## 1. Вимоги

- Windows Server 2019+ або Windows 10/11
- [Python 3.11+](https://www.python.org/downloads/) — при інсталяції ✅ **Add to PATH**
- Доступ в інтернет (Telegram API, OpenRouter, Cloudflare Worker)

## 2. Завантаження

```powershell
cd C:\
git clone https://github.com/cayz696/okdev-win.git
cd okdev-win\bot
```

Або скопіюй папку `bot` на сервер через RDP.

## 3. Встановлення (один раз)

```powershell
cd C:\okdev-win\bot
.\install.ps1
```

Скрипт створить `.venv`, встановить залежності, скопіює `.env.example` → `.env`.

## 4. Налаштуй `.env`

Відкрий `C:\okdev-win\bot\.env`:

```env
TELEGRAM_BOT_TOKEN=...
WORKER_URL=https://portfolio-contact-form.cayz696.workers.dev
PUBLISH_SECRET=...
ALLOWED_USER_IDS=твій_telegram_id
OPENROUTER_API_KEY=sk-or-v1-...
TELEGRAM_CHANNEL_ID=@твій_канал
```

`ALLOWED_USER_IDS` — твій числовий ID (дізнайся у @userinfobot).

## 5. Запуск

**Вручну (тест):**
```powershell
cd C:\okdev-win\bot
.\run.ps1
```

**Автозапуск (Task Scheduler):**
```powershell
# PowerShell від Адміністратора
cd C:\okdev-win\bot
.\register-task.ps1
```

Перевір: `Get-ScheduledTask -TaskName "OkdevBlogBot"`

## 6. Користування

1. Відкрий бота в Telegram → `/start`
2. Кнопки:
   - **📝 AI-пост** — тема → AI → публікація
   - **💡 Моя ідея** — кидаєш ідею → AI розгортає
   - **📅 План на тиждень** — 7 днів → обери день
   - **⚙️ Налаштування** — канал для постингу
3. Додай бота **адміном** у Telegram-канал

## 7. Промпти AI

Редагуй `bot/prompts.py` — там 3 промпти:
- `POST_FROM_TOPIC_*` — пост з теми
- `POST_FROM_IDEA_*` — пост з твоєї ідеї
- `WEEKLY_PLAN` — план на 7 днів

## 8. Логи / помилки

- Консоль при `.\run.ps1`
- Task Scheduler → History
- Бот сам показує помилки в Telegram з кнопкою «Меню»

## 9. Оновлення

```powershell
cd C:\okdev-win
git pull
cd bot
.\install.ps1
# Перезапусти задачу або run.ps1
```
