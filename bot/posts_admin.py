"""List and delete posts on okdev.win via Worker API."""

import logging

import httpx

from config import PUBLISH_SECRET, SITE_DOMAIN, WORKER_URL

log = logging.getLogger(__name__)


class PostsAdminError(Exception):
    pass


async def list_site_posts(lang: str = "", limit: int = 30) -> list[dict]:
    if not WORKER_URL:
        raise PostsAdminError("WORKER_URL не налаштований")

    params = {"limit": str(limit)}
    if lang:
        params["lang"] = lang

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f"{WORKER_URL}/posts", params=params)

    try:
        data = res.json()
    except Exception:
        data = {}

    if not res.is_success or not data.get("ok"):
        raise PostsAdminError(data.get("error", "Не вдалося завантажити пости"))

    return data.get("posts") or []


async def delete_site_post(slug: str) -> dict:
    if not WORKER_URL or not PUBLISH_SECRET:
        raise PostsAdminError("WORKER_URL або PUBLISH_SECRET не налаштовані")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.delete(
            f"{WORKER_URL}/posts/{slug}",
            headers={"X-Publish-Secret": PUBLISH_SECRET},
        )

    try:
        data = res.json()
    except Exception:
        data = {}

    if not res.is_success or not data.get("ok"):
        raise PostsAdminError(data.get("error", "Не вдалося видалити пост"))

    return data


def post_admin_url(slug: str, lang: str) -> str:
    base = "/en/blog" if lang == "en" else "/blog"
    return f"{SITE_DOMAIN.rstrip('/')}{base}/{slug}/"
