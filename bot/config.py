import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WORKER_URL = os.getenv("WORKER_URL", "").rstrip("/")
PUBLISH_SECRET = os.getenv("PUBLISH_SECRET", "")
ALLOWED_IDS = {int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()}

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite")
OPENROUTER_IMAGE_MODEL = os.getenv(
    "OPENROUTER_IMAGE_MODEL",
    "google/gemini-3.1-flash-lite-image",
)
# gemini = Gemini + logo overlay (default). brand = free Pillow template only.
COVER_MODE = os.getenv("COVER_MODE", "gemini").strip().lower()
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "https://www.okdev.win")
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Kyiv")

DEFAULT_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
SETTINGS_FILE = os.getenv("BOT_SETTINGS_FILE", "data/settings.json")
SCHEDULE_FILE = os.getenv("BOT_SCHEDULE_FILE", "data/schedule.json")
PREVIEWS_FILE = os.getenv("BOT_PREVIEWS_FILE", "data/plan_previews.json")
PLAN_FILE = os.getenv("BOT_PLAN_FILE", "data/weekly_plan.json")
SCHEDULE_CHECK_SECONDS = int(os.getenv("SCHEDULE_CHECK_SECONDS", "120"))
