/* =========================================================================
   Cloudflare Worker — contact form + blog publish bridge + image storage
   ========================================================================= */

const ALLOWED_ORIGINS = ["https://okdev.win", "https://www.okdev.win"];

const POSTS_KEY = "posts";
const MAX_POSTS_STORED = 200;
const MAX_IMAGE_BYTES = 2 * 1024 * 1024; // 2 MB
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 8;

function isAllowedOrigin(origin) {
  return ALLOWED_ORIGINS.includes(origin);
}

function corsHeaders(origin) {
  const allow = isAllowedOrigin(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Publish-Secret",
    "Vary": "Origin",
  };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function slugify(title) {
  return String(title)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\u0400-\u04FF]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || crypto.randomUUID().slice(0, 8);
}

async function checkRateLimit(request, env) {
  if (!env.POSTS_KV) return true;
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const key = `rl:${ip}`;
  const now = Date.now();
  const raw = await env.POSTS_KV.get(key);
  let bucket = raw ? JSON.parse(raw) : { count: 0, reset: now + RATE_LIMIT_WINDOW_MS };
  if (now > bucket.reset) bucket = { count: 0, reset: now + RATE_LIMIT_WINDOW_MS };
  bucket.count += 1;
  await env.POSTS_KV.put(key, JSON.stringify(bucket), { expirationTtl: 120 });
  return bucket.count <= RATE_LIMIT_MAX;
}

async function sendTelegram(env, chatId, text) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });
}

async function handleContactForm(request, env, origin) {
  if (!isAllowedOrigin(origin)) {
    return json({ ok: false, error: "Forbidden" }, 403, origin || ALLOWED_ORIGINS[0]);
  }

  if (!(await checkRateLimit(request, env))) {
    return json({ ok: false, error: "Rate limit exceeded" }, 429, origin);
  }

  let data;
  try {
    data = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON" }, 400, origin);
  }

  if (data.website) return json({ ok: true }, 200, origin);

  const name = (data.name || "").toString().trim().slice(0, 200);
  const contact = (data.contact || "").toString().trim().slice(0, 200);
  const type = (data.type || "").toString().trim().slice(0, 100);
  const message = (data.message || "").toString().trim().slice(0, 3000);

  if (!name || !contact || !message) {
    return json({ ok: false, error: "Missing required fields" }, 400, origin);
  }

  const text =
    "🆕 <b>Нова заявка з сайту</b>\n\n" +
    `👤 <b>Ім'я:</b> ${esc(name)}\n` +
    `📞 <b>Контакт:</b> ${esc(contact)}\n` +
    `🗂 <b>Тип проєкту:</b> ${esc(type || "—")}\n\n` +
    `💬 <b>Повідомлення:</b>\n${esc(message)}`;

  const tgRes = await sendTelegram(env, env.TELEGRAM_CHAT_ID, text);
  if (!tgRes.ok) return json({ ok: false, error: "Telegram API error" }, 502, origin);
  return json({ ok: true }, 200, origin);
}

async function loadPosts(env) {
  const raw = await env.POSTS_KV.get(POSTS_KEY);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function savePosts(env, posts) {
  await env.POSTS_KV.put(POSTS_KEY, JSON.stringify(posts.slice(0, MAX_POSTS_STORED)));
}

function publicPost(p) {
  const { imageData, imageMime, ...rest } = p;
  return rest;
}

async function handlePostsGet(request, env, origin) {
  if (!env.POSTS_KV) return json({ ok: false, error: "POSTS_KV not configured" }, 500, origin);

  const url = new URL(request.url);
  const lang = (url.searchParams.get("lang") || "").trim();
  const limit = Math.min(parseInt(url.searchParams.get("limit") || "20", 10) || 20, 50);
  const offset = Math.max(parseInt(url.searchParams.get("offset") || "0", 10) || 0, 0);

  let posts = await loadPosts(env);
  const now = new Date().toISOString();
  posts = posts.filter((p) => !p.scheduledAt || p.scheduledAt <= now);
  if (lang) posts = posts.filter((p) => p.lang === lang);

  const total = posts.length;
  const slice = posts.slice(offset, offset + limit).map(publicPost);

  return new Response(
    JSON.stringify({ ok: true, posts: slice, total, offset, limit, hasMore: offset + limit < total }),
    {
      status: 200,
      headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=300", ...corsHeaders(origin) },
    },
  );
}

async function handlePostBySlug(request, env, origin, slug) {
  if (!env.POSTS_KV) return json({ ok: false, error: "POSTS_KV not configured" }, 500, origin);

  const url = new URL(request.url);
  const lang = (url.searchParams.get("lang") || "").trim();
  const posts = await loadPosts(env);
  const now = new Date().toISOString();

  const post = posts.find((p) => {
    const match = p.slug === slug || p.id === slug;
    const published = !p.scheduledAt || p.scheduledAt <= now;
    const langOk = !lang || p.lang === lang;
    return match && published && langOk;
  });

  if (!post) return json({ ok: false, error: "Not found" }, 404, origin);
  return json({ ok: true, post: publicPost(post) }, 200, origin);
}

async function storeImage(env, imageId, imageBase64, imageMime) {
  if (!imageBase64 || !env.POSTS_KV) return null;
  const raw = imageBase64.replace(/^data:[^;]+;base64,/, "");
  const approxBytes = Math.ceil((raw.length * 3) / 4);
  if (approxBytes > MAX_IMAGE_BYTES) return null;

  await env.POSTS_KV.put(`img:${imageId}`, JSON.stringify({ data: raw, mime: imageMime || "image/jpeg" }));
  return imageId;
}

async function handleImageGet(env, imageId, origin) {
  if (!env.POSTS_KV) return new Response("Not found", { status: 404 });
  const raw = await env.POSTS_KV.get(`img:${imageId}`);
  if (!raw) return new Response("Not found", { status: 404 });

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return new Response("Not found", { status: 404 });
  }

  const bytes = Uint8Array.from(atob(parsed.data), (c) => c.charCodeAt(0));
  return new Response(bytes, {
    status: 200,
    headers: {
      "Content-Type": parsed.mime || "image/jpeg",
      "Cache-Control": "public, max-age=86400",
      ...corsHeaders(origin),
    },
  });
}

async function handlePostsPublish(request, env, origin) {
  if (!env.POSTS_KV) return json({ ok: false, error: "POSTS_KV not configured" }, 500, origin);

  const secret = request.headers.get("X-Publish-Secret") || "";
  if (!env.PUBLISH_SECRET || secret !== env.PUBLISH_SECRET) {
    return json({ ok: false, error: "Unauthorized" }, 401, origin);
  }

  let data;
  try {
    data = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON" }, 400, origin);
  }

  const lang = (data.lang || "").toString().trim();
  const title = (data.title || "").toString().trim().slice(0, 200);
  const summary = (data.summary || "").toString().trim().slice(0, 400);
  const body = (data.body || "").toString().trim().slice(0, 10000);
  const tags = Array.isArray(data.tags) ? data.tags.slice(0, 8).map((t) => String(t).slice(0, 40)) : [];
  const keywords = Array.isArray(data.keywords)
    ? data.keywords.slice(0, 12).map((k) => String(k).slice(0, 60))
    : [];
  const slug = (data.slug || slugify(title)).toString().trim().slice(0, 80);
  const scheduledAt = data.scheduledAt ? String(data.scheduledAt).slice(0, 30) : null;
  const imageBase64 = data.imageBase64 ? String(data.imageBase64) : "";
  const imageMime = (data.imageMime || "image/jpeg").toString().slice(0, 40);

  if (!["uk", "en"].includes(lang) || !title || !body) {
    return json({ ok: false, error: "lang (uk|en), title and body are required" }, 400, origin);
  }

  const posts = await loadPosts(env);
  if (posts.some((p) => p.slug === slug)) {
    return json({ ok: false, error: "Slug already exists" }, 409, origin);
  }

  const id = crypto.randomUUID();
  let imageId = null;

  if (imageBase64) {
    imageId = `img-${id.slice(0, 8)}`;
    const stored = await storeImage(env, imageId, imageBase64, imageMime);
    if (!stored) imageId = null;
  }

  const post = {
    id,
    slug,
    lang,
    title,
    summary: summary || body.slice(0, 200),
    body,
    tags,
    keywords,
    imageId,
    scheduledAt,
    publishedAt: scheduledAt && scheduledAt > new Date().toISOString() ? scheduledAt : new Date().toISOString(),
  };

  posts.unshift(post);
  await savePosts(env, posts);

  return json({ ok: true, id: post.id, slug: post.slug, imageId }, 200, origin);
}

async function handlePostDelete(request, env, origin, slug) {
  if (!env.POSTS_KV) return json({ ok: false, error: "POSTS_KV not configured" }, 500, origin);

  const secret = request.headers.get("X-Publish-Secret") || "";
  if (!env.PUBLISH_SECRET || secret !== env.PUBLISH_SECRET) {
    return json({ ok: false, error: "Unauthorized" }, 401, origin);
  }

  const posts = await loadPosts(env);
  const idx = posts.findIndex((p) => p.slug === slug || p.id === slug);
  if (idx === -1) return json({ ok: false, error: "Not found" }, 404, origin);

  const [removed] = posts.splice(idx, 1);
  await savePosts(env, posts);
  if (removed.imageId) {
    await env.POSTS_KV.delete(`img:${removed.imageId}`);
  }

  return json({ ok: true, slug: removed.slug, title: removed.title }, 200, origin);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin) });
    }

    const imageMatch = url.pathname.match(/^\/images\/([^/]+)$/);
    if (imageMatch && request.method === "GET") {
      return handleImageGet(env, imageMatch[1], origin);
    }

    if (url.pathname === "/posts") {
      if (request.method === "GET") return handlePostsGet(request, env, origin);
      if (request.method === "POST") return handlePostsPublish(request, env, origin);
      return json({ ok: false, error: "Method not allowed" }, 405, origin);
    }

    const postMatch = url.pathname.match(/^\/posts\/([^/]+)$/);
    if (postMatch) {
      const slug = decodeURIComponent(postMatch[1]);
      if (request.method === "GET") return handlePostBySlug(request, env, origin, slug);
      if (request.method === "DELETE") return handlePostDelete(request, env, origin, slug);
      return json({ ok: false, error: "Method not allowed" }, 405, origin);
    }

    if (request.method !== "POST") {
      return json({ ok: false, error: "Method not allowed" }, 405, origin);
    }
    return handleContactForm(request, env, origin);
  },
};
