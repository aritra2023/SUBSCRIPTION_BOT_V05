import os
import json
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Bot token (separate from main payment bot) ────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_DEMO_BOT_TOKEN")

# ── Storage channel where all files are silently kept ─────────────────────────
STORAGE_CHANNEL_ID = -1003930510795

# ── Admins (same as main bot — only they can store files) ─────────────────────
ADMIN_IDS = {7342290214, 6490401448, 5575466305}

# ── Custom button config (persisted to disk) ──────────────────────────────────
_BUTTON_FILE = os.path.join(os.path.dirname(__file__), "button.json")

def get_custom_button() -> dict | None:
    """Return {"url": ..., "text": ...} or None."""
    try:
        with open(_BUTTON_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def set_custom_button(url: str, text: str) -> None:
    with open(_BUTTON_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url, "text": text}, f)

def remove_custom_button() -> None:
    try:
        os.remove(_BUTTON_FILE)
    except FileNotFoundError:
        pass
