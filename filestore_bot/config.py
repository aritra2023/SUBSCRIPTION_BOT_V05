import os
import json
import uuid
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_DIR = os.path.dirname(__file__)

# ── Bot token ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_DEMO_BOT_TOKEN")

# ── Storage channel ───────────────────────────────────────────────────────────
STORAGE_CHANNEL_ID = -1003930510795

# ── Admin IDs ─────────────────────────────────────────────────────────────────
ADMIN_IDS = {7342290214, 6490401448, 5575466305}

# ─────────────────────────────────────────────────────────────────────────────
# Buttons — global + per-file/per-batch
# Stored as: { "global": {url, text}, "<id>": {url, text}, ... }
# ─────────────────────────────────────────────────────────────────────────────
_BUTTON_FILE = os.path.join(_DIR, "button.json")

def _load_buttons() -> dict:
    try:
        with open(_BUTTON_FILE, encoding="utf-8") as f:
            data = json.load(f)
            # migrate old flat format {"url":..,"text":..} → {"global":{..}}
            if "url" in data:
                data = {"global": data}
            return data
    except Exception:
        return {}

def _save_buttons(data: dict) -> None:
    with open(_BUTTON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def get_button(target_id: str | None = None) -> dict | None:
    """
    Return button for target_id if set, else the global button, else None.
    target_id = str(msg_id) for single files, or batch_id string for batches.
    """
    data = _load_buttons()
    if target_id and str(target_id) in data:
        return data[str(target_id)]
    return data.get("global")

def set_button(url: str, text: str, target_id: str | None = None) -> None:
    data = _load_buttons()
    key  = str(target_id) if target_id else "global"
    data[key] = {"url": url, "text": text}
    _save_buttons(data)

def remove_button(target_id: str | None = None) -> None:
    data = _load_buttons()
    key  = str(target_id) if target_id else "global"
    data.pop(key, None)
    _save_buttons(data)

# ── Legacy aliases (used nowhere new, kept for safety) ────────────────────────
def get_custom_button():      return get_button()
def set_custom_button(u, t):  set_button(u, t)
def remove_custom_button():   remove_button()

# ─────────────────────────────────────────────────────────────────────────────
# Running batch  →  per-admin list being built right now
# ─────────────────────────────────────────────────────────────────────────────
_RUNNING_FILE = os.path.join(_DIR, "running_batches.json")

def _load_running() -> dict:
    try:
        with open(_RUNNING_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_running(data: dict) -> None:
    with open(_RUNNING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def get_running_batch(admin_id: int) -> list[int]:
    return _load_running().get(str(admin_id), [])

def add_to_running_batch(admin_id: int, msg_id: int) -> list[int]:
    data = _load_running()
    key  = str(admin_id)
    data.setdefault(key, [])
    if msg_id not in data[key]:
        data[key].append(msg_id)
    _save_running(data)
    return data[key]

def clear_running_batch(admin_id: int) -> None:
    data = _load_running()
    data.pop(str(admin_id), None)
    _save_running(data)

# ─────────────────────────────────────────────────────────────────────────────
# Saved batches  →  finalized batches with a shareable ID
# ─────────────────────────────────────────────────────────────────────────────
_BATCHES_FILE = os.path.join(_DIR, "batches.json")

def _load_batches() -> dict:
    try:
        with open(_BATCHES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_batches(data: dict) -> None:
    with open(_BATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def save_batch(msg_ids: list[int]) -> str:
    batch_id = uuid.uuid4().hex[:10]
    data = _load_batches()
    data[batch_id] = msg_ids
    _save_batches(data)
    return batch_id

def get_batch(batch_id: str) -> list[int] | None:
    return _load_batches().get(batch_id)
