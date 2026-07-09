import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WORKER_URL = os.getenv("WORKER_URL", "").rstrip("/")
PUBLISH_SECRET = os.getenv("PUBLISH_SECRET", "")
ALLOWED_IDS = {int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()}

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "https://www.okdev.win")
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Kyiv")

DEFAULT_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
SETTINGS_FILE = os.getenv("BOT_SETTINGS_FILE", "data/settings.json")
