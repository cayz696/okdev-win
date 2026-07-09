# Cloudflare Worker — форма + блог + зображення

## Cloudflare ≠ Worker (коротко)

**Cloudflare** — це платформа (акаунт, DNS, SSL, захист).

У твоєму проєкті на Cloudflare працюють **дві окремі речі**:

| Сервіс | Що робить | URL |
|--------|-----------|-----|
| **Cloudflare Pages** | Хостить статичний сайт (HTML/CSS/JS) | `https://www.okdev.win` |
| **Cloudflare Worker** | API на edge: форма → Telegram, блог, картинки | `https://portfolio-contact-form.ТВІЙ_АКАУНТ.workers.dev` |

Сайт і Worker — **різні URL**, але в одному акаунті Cloudflare. Сайт викликає Worker через `fetch()` з `assets/config.js`.

```
Браузер → www.okdev.win (Pages) → fetch → Worker → Telegram / KV
Бот на VPS → Worker /posts → KV
```

---

## Worker обслуговує

1. **POST /** — заявки з форми → Telegram
2. **GET/POST /posts** — блог (читання публічне, публікація з секретом)
3. **GET /images/{id}** — зображення постів

---

## Покроковий деплой

### Крок 0. Акаунт Cloudflare

1. Зареєструйся на [cloudflare.com](https://cloudflare.com)
2. Додай домен `okdev.win` → Cloudflare стане DNS
3. У реєстратора домену вкажи nameservers від Cloudflare

### Крок 1. Статичний сайт (Pages)

1. Dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** (або Upload)
2. Підключи репозиторій або завантаж папку проєкту
3. Build settings: **Framework preset = None**, build command порожній, output = `/` (корінь)
4. Deploy → отримаєш `*.pages.dev`
5. **Custom domains** → додай `okdev.win` і `www.okdev.win`
6. Файл `_redirects` підхопиться автоматично (блог `/blog/slug/`)

### Крок 2. Worker (API)

#### Варіант A — через термінал (рекомендовано)

```bash
npm install -g wrangler
cd worker
wrangler login

# Створи KV-сховище для блогу
wrangler kv namespace create POSTS_KV
# Скопіюй id у wrangler.toml → kv_namespaces[0].id

# Секрети (НЕ коміть у git!)
wrangler secret put TELEGRAM_BOT_TOKEN    # бот для форми (окремий від publish-бота)
wrangler secret put TELEGRAM_CHAT_ID      # chat_id куди падатимуть заявки
wrangler secret put PUBLISH_SECRET        # довгий випадковий рядок для публікації блогу

wrangler deploy
```

Після `wrangler deploy` у терміналі з'явиться URL, наприклад:
`https://portfolio-contact-form.emojiestore.workers.dev`

#### Варіант B — через Dashboard (без термінала)

1. **Workers & Pages** → **Create** → **Worker**
2. Встав код з `worker/worker.js`
3. **Settings** → **Variables** → додай secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PUBLISH_SECRET`
4. **KV** → Create namespace `POSTS_KV` → прив'яжи binding `POSTS_KV` у Worker
5. Deploy → скопіюй URL

### Крок 3. Підключити Worker до сайту

У `assets/config.js`:

```js
workerUrl: "https://portfolio-contact-form.ТВІЙ_АКАУНТ.workers.dev",
```

Задеплой сайт знову (Pages підхопить зміну автоматично з Git).

### Крок 4. Перевірка

```bash
# Блог (має повернути {"ok":true,"posts":[]})
curl "https://ТВІЙ_WORKER_URL/posts?lang=uk"

# Форма (має повернути помилку полів — це нормально, головне не 403)
curl -X POST "https://ТВІЙ_WORKER_URL/" \
  -H "Content-Type: application/json" \
  -H "Origin: https://www.okdev.win" \
  -d '{"name":"Test","contact":"@test","message":"hi"}'
```

Заповни форму на сайті — заявка має прийти в Telegram.

---

## API блогу

### POST /posts (захищено)

```
Header: X-Publish-Secret: <PUBLISH_SECRET>

{
  "lang": "uk",
  "title": "Заголовок",
  "body": "Текст статті",
  "summary": "Короткий опис",
  "slug": "url-slug",
  "keywords": ["бот для магазину", "замовити бота"],
  "tags": ["Telegram"],
  "scheduledAt": "2026-07-10T09:00:00+03:00",
  "imageBase64": "data:image/jpeg;base64,...",
  "imageMime": "image/jpeg"
}
```

### GET /posts?lang=uk&limit=20

Список опублікованих постів (з урахуванням `scheduledAt`).

### GET /posts/{slug}?lang=uk

Окремий пост.

### GET /images/{imageId}

Зображення поста (кеш 24 год).

---

## Telegram-бот для публікації

Окремий бот на VPS: `bot/publish_bot.py` — див. `bot/README.md`.

Контент-план на 7 днів: `content-plan-week.md`.

---

## Безпека

- Токен Telegram для форми — **тільки** у Worker secrets
- `PUBLISH_SECRET` — для публікації постів (Worker + `.env` бота)
- Форма приймає запити **тільки** з `https://okdev.win` / `https://www.okdev.win`
- Rate limit: 8 запитів/хв на IP
- Honeypot на клієнті та сервері
- Унікальність `slug` при публікації
