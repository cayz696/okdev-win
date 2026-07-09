from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Draft:
    lang: str = "uk"
    title: str = ""
    summary: str = ""
    body: str = ""
    keywords: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    slug: str = ""
    scheduled_at: str = ""
    image_bytes: bytes = b""
    image_mime: str = "image/jpeg"
    source_topic: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("image_bytes", None)
        return d

    @classmethod
    def from_ai(cls, data: dict) -> "Draft":
        return cls(
            lang=data.get("lang", "uk"),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            body=data.get("body", ""),
            keywords=data.get("keywords", []) if isinstance(data.get("keywords"), list) else [],
            tags=data.get("tags", []) if isinstance(data.get("tags"), list) else [],
            slug=data.get("slug", ""),
            scheduled_at=data.get("scheduledAt", data.get("scheduled_at", "")),
            source_topic=data.get("source_topic", ""),
        )

    def preview_text(self, max_body: int = 500) -> str:
        kw = ", ".join(self.keywords) or "—"
        tags = ", ".join(self.tags) or "—"
        body = (self.body[:max_body] + "…") if len(self.body) > max_body else self.body
        photo = "📷 так" if self.image_bytes else "—"
        return (
            f"📝 Чернетка ({self.lang})\n\n"
            f"<b>{self.title or '—'}</b>\n"
            f"{self.summary or '—'}\n\n"
            f"Slug: <code>{self.slug or '—'}</code>\n"
            f"Keywords: {kw}\n"
            f"Tags: {tags}\n"
            f"Фото: {photo}\n"
            f"Schedule: {self.scheduled_at or '—'}\n\n"
            f"{body}"
        )

    def post_url(self) -> str:
        base = "/en/blog" if self.lang == "en" else "/blog"
        slug = self.slug or "post"
        return f"{base}/{slug}/"
