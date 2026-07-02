import logging
from datetime import datetime, timezone
from telegram import InlineKeyboardMarkup
from telegram.constants import ParseMode
from config import users_col, pays_col, ADMIN_IDS

logger = logging.getLogger(__name__)

# ── Font helpers ───────────────────────────────────────────────────────────────
def u(text):
    SC = {
        'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ғ','g':'ɢ','h':'ʜ',
        'i':'ɪ','j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ',
        'q':'Q','r':'ʀ','s':'s','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x',
        'y':'ʏ','z':'ᴢ',
    }
    return ''.join(SC.get(c, c) for c in text)

def b(text):
    return f"<b>{u(text)}</b>"

# ── Auth ───────────────────────────────────────────────────────────────────────
def is_admin(user) -> bool:
    return user.id in ADMIN_IDS

# ── Database helpers ───────────────────────────────────────────────────────────
def save_user(user):
    """Upsert user record in MongoDB."""
    users_col.update_one(
        {"user_id": user.id},
        {"$set": {
            "username":   user.username,
            "first_name": user.first_name,
            "last_name":  user.last_name,
            "last_seen":  datetime.now(timezone.utc),
        }, "$setOnInsert": {"joined_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

def record_payment(user_id, plan, ref_id, pay_type) -> bool:
    """Record a successful payment (idempotent on ref_id).
    Returns True if newly inserted, False if already recorded."""
    result = pays_col.update_one(
        {"ref_id": ref_id},
        {"$setOnInsert": {
            "user_id":    user_id,
            "plan_id":    plan["id"],
            "plan_name":  plan["channel"],
            "amount":     plan["price"],
            "pay_type":   pay_type,
            "ref_id":     ref_id,
            "paid_at":    datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return result.upserted_id is not None

# ── Telegram helpers ───────────────────────────────────────────────────────────
async def safe_edit(query, context, text, keyboard, parse_mode=ParseMode.HTML):
    """Edit a message safely, falling back to send_message if needed."""
    rm = InlineKeyboardMarkup(keyboard)
    try:
        if query.message.photo or query.message.document or query.message.video:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text, reply_markup=rm, parse_mode=parse_mode,
            )
        else:
            await query.edit_message_text(text, reply_markup=rm, parse_mode=parse_mode)
    except Exception as e:
        logger.warning(f"safe_edit fallback: {e}")
        try:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text, reply_markup=rm, parse_mode=parse_mode,
            )
        except Exception as e2:
            logger.error(f"safe_edit final error: {e2}")
