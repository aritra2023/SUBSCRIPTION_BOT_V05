import os
import logging
import razorpay
from datetime import datetime, timezone
from pymongo import MongoClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Environment ───────────────────────────────────────────────────────────────
BOT_TOKEN            = os.environ["TELEGRAM_BOT_TOKEN"]
RAZORPAY_KEY_ID      = os.environ["RAZORPAY_KEY_ID"]
RAZORPAY_KEY_SECRET  = os.environ["RAZORPAY_KEY_SECRET"]
MONGODB_URI          = os.environ["MONGODB_URI"]
ADMIN_USERNAME       = "aritramahatma"
ADMIN_IDS            = {7342290214}
PREMIUM_CHANNEL_LINK = "https://t.me/+K2hQ7Cdgm1Y3MjY1"
FREE_CHANNEL_LINK    = "https://t.me/+K2hQ7Cdgm1Y3MjY1"   # update to your free channel
CRYPTO_NETWORK       = "BNB Smart Chain (BEP20)"
CRYPTO_ADDRESS       = "0x2c191f92fad334dc3c650e8a315bd1a4b4c77781"

# ── Razorpay ──────────────────────────────────────────────────────────────────
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ── MongoDB ───────────────────────────────────────────────────────────────────
mongo     = MongoClient(MONGODB_URI)
db        = mongo["paybot"]
users_col = db["users"]
pays_col  = db["payments"]
plans_col = db["plans"]

# ── In-memory state ───────────────────────────────────────────────────────────
pending_payments   = {}   # user_id → payment info
pending_recharges  = {}   # user_id → recharge info
pending_broadcasts = {}   # admin_id → {chat_id, message_id}

# ── Plans (MongoDB-backed) ────────────────────────────────────────────────────
_SEED_PLANS = [
    {"id": "hawt",  "channel": "Plan 1 - HAWT PACK",                "description": "<b>ʜᴀᴡᴛ ᴘᴀᴄᴋ</b>", "price": 199, "pay_description": "Subscription: HAWT PACK"},
    {"id": "desi",  "channel": "Plan 2 - DESI PACK",                "description": "<b>ᴅᴇsɪ ᴘᴀᴄᴋ</b>", "price": 299, "pay_description": "Subscription: DESI PACK"},
    {"id": "snap",  "channel": "Plan 3 - OG SNAP PACK",             "description": "<b>ᴏɢ sɴᴀᴘ ᴘᴀᴄᴋ</b>", "price": 399, "pay_description": "Subscription: OG SNAP PACK"},
    {"id": "rare",  "channel": "Plan 4 - RARE IRL AND EPIC 2 IN 1", "description": "<b>ʀᴀʀᴇ ɪʀʟ &amp; ᴇᴘɪᴄ</b>", "price": 499, "pay_description": "Subscription: RARE IRL AND EPIC"},
    {"id": "combo", "channel": "Plan 5 - Combo All Plans",           "description": "<b>ᴄᴏᴍʙᴏ ᴀʟʟ ᴘʟᴀɴs</b>", "price": 699, "pay_description": "Subscription: Combo All Plans"},
    {"id": "famp",  "channel": "Plan 6 - FAMP EXCLUSIVE",            "description": "<b>ғᴀᴍᴘ ᴇxᴄʟᴜsɪᴠᴇ</b>", "price": 999, "pay_description": "Subscription: FAMP EXCLUSIVE"},
]
if plans_col.count_documents({}) == 0:
    plans_col.insert_many(_SEED_PLANS)

def get_all_plans():
    return list(plans_col.find({}, {"_id": 0}).sort("created_at", -1))

def get_plan(pid):
    return plans_col.find_one({"id": pid}, {"_id": 0})
