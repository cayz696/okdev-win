# Telegram-бот для публікації блогу

Окремий бот (на VPS або локально) публікує пости на сайт через Cloudflare Worker API.
Сайт залишається статичним — бот лише «скидає» схвалений контент у KV-сховище.

## Налаштування

1. Задеплой Worker (`worker/README.md`) з KV namespace і секретом `PUBLISH_SECRET`.
2. Створи Telegram-бота через [@BotFather](https://t.me/BotFather).
3. Скопіюй `.env.example` → `.env` і заповни значення.
4. Запусти: `python publish_bot.py`

### Автозапуск на VPS (systemd)

```bash
# На сервері
cd bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заповни значення
chmod 600 .env

# Підстав свої шляхи в portfolio-bot.service.example
sudo cp portfolio-bot.service.example /etc/systemd/system/portfolio-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now portfolio-bot
sudo systemctl status portfolio-bot
```

## Команди бота

| Команда | Опис |
|---------|------|
| `/start` | Привітання та інструкція |
| `/post uk` або `/post en` | Почати новий пост (далі — фото або текст) |
| `/publish` | Опублікувати чернетку на сайт |
| `/schedule 2026-07-10T09:00:00+03:00` | Запланувати публікацію |
| `/cancel` | Скасувати чернетку |

## Формат поста

### Варіант 1: Фото + підпис

Надішли фото, а в підписі (caption):

```
title: Telegram-бот для магазину: 5 функцій
summary: Які можливості бота окупаються за місяць
keywords: бот для магазину, замовити бота, автоматизація продажів
tags: Telegram, E-commerce
slug: telegram-bot-magazin-5-funktsiy

Основний текст статті.
Кілька абзаців — кожен через порожній рядок.
```

### Варіант 2: Тільки текст

```
/post uk

title: Заголовок
summary: Короткий опис
keywords: ключ1, ключ2
tags: Тег1
slug: url-slug

Текст статті.
```

## SEO-ключі

Поле `keywords` — **обов'язкове для SEO**. Правила:

- 3–7 ключових фраз на пост
- Включай головний ключ у `title` і перший абзац `body`
- Використовуй довгі хвости: «бот для інтернет магазину», а не просто «бот»
- Для EN-постів — англомовні ключі з `README.md` (розділ SEO)

Ключі потрапляють у:
- JSON-LD `BlogPosting` на сторінці поста
- Прихований блок `.blog-keywords` у картці (для індексації)
- Мета `description` (через `summary`)

## API Worker (для кастомної інтеграції)

### POST /posts

```
Headers:
  Content-Type: application/json
  X-Publish-Secret: <PUBLISH_SECRET>

Body:
{
  "lang": "uk",              // uk | en
  "title": "...",            // обов'язково
  "body": "...",             // обов'язково
  "summary": "...",          // для картки та meta description
  "slug": "...",             // URL: /blog/{slug}/ (авто з title якщо не вказано)
  "keywords": ["...", "..."], // SEO-ключі
  "tags": ["...", "..."],
  "scheduledAt": "2026-07-10T09:00:00+03:00",  // опційно, ISO 8601
  "imageBase64": "data:image/jpeg;base64,...",  // опційно, до 2 MB
  "imageMime": "image/jpeg"
}
```

### GET /posts?lang=uk&limit=20

Публічний список постів (без секрету).

### GET /posts/{slug}?lang=uk

Окремий пост за slug.

### GET /images/{imageId}

Зображення поста (публічне).

## Публікація контент-плану

Готові 7 постів — у `content-plan-week.md`. Публікуй вручну через бота (`/post uk` → текст → `/publish`) або через `POST /posts` API Worker.
