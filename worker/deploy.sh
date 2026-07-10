#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== 1. Login (якщо ще не залогінений) ==="
npx wrangler whoami || npx wrangler login

echo ""
echo "=== 2. KV namespace (якщо id ще REPLACE в wrangler.toml) ==="
if grep -q "REPLACE_WITH_KV_NAMESPACE_ID" wrangler.toml; then
  npx wrangler kv namespace create POSTS_KV
  echo "Скопіюй id зверху в wrangler.toml → kv_namespaces[0].id"
  echo "Потім запусти скрипт знову."
  exit 0
fi

echo ""
echo "=== 3. Secrets ==="
echo "Введи TELEGRAM_BOT_TOKEN (бот для форми з BotFather):"
npx wrangler secret put TELEGRAM_BOT_TOKEN
echo "Введи TELEGRAM_CHAT_ID (куди падатимуть заявки):"
npx wrangler secret put TELEGRAM_CHAT_ID
echo "Введи PUBLISH_SECRET (довгий випадковий рядок для блогу):"
npx wrangler secret put PUBLISH_SECRET

echo ""
echo "=== 4. Deploy ==="
npx wrangler deploy

echo ""
echo "Готово! Скопіюй URL Worker у assets/config.js → workerUrl"
