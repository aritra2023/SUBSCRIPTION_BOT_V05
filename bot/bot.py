import os
import logging
import razorpay
import io
import time
import urllib.request
from datetime import datetime, timezone
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Env ───────────────────────────────────────────────────────────────────────
BOT_TOKEN          = os.environ["TELEGRAM_BOT_TOKEN"]
RAZORPAY_KEY_ID    = os.environ["RAZORPAY_KEY_ID"]
RAZORPAY_KEY_SECRET= os.environ["RAZORPAY_KEY_SECRET"]
MONGODB_URI        = os.environ["MONGODB_URI"]
ADMIN_USERNAME     = "aritramahatma"        # without @
ADMIN_IDS          = {7342290214}           # numeric admin IDs
PREMIUM_CHANNEL_LINK = "https://t.me/+K2hQ7Cdgm1Y3MjY1"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ── MongoDB ───────────────────────────────────────────────────────────────────
mongo     = MongoClient(MONGODB_URI)
db        = mongo["paybot"]
users_col = db["users"]
pays_col  = db["payments"]

# ── In-memory ─────────────────────────────────────────────────────────────────
pending_payments    = {}   # user_id → payment info
pending_broadcasts  = {}   # admin_id → {chat_id, message_id}

# ── Font helpers ──────────────────────────────────────────────────────────────
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

# ── Plans ─────────────────────────────────────────────────────────────────────
PLANS = [
    {"id": "hawt",  "channel": "Plan 1 - HAWT PACK",               "category": "SNAP PRIME", "price": 199},
    {"id": "desi",  "channel": "Plan 2 - DESI PACK",               "category": "SNAP PRIME", "price": 299},
    {"id": "snap",  "channel": "Plan 3 - OG SNAP PACK",            "category": "SNAP PRIME", "price": 399},
    {"id": "rare",  "channel": "Plan 4 - RARE IRL AND EPIC 2 IN 1","category": "EPIC PRIME", "price": 499},
    {"id": "combo", "channel": "Plan 5 - Combo All Plans",          "category": "MEGA PRIME", "price": 699},
    {"id": "famp",  "channel": "Plan 6 - FAMP EXCLUSIVE",           "category": "FAMP PRIME", "price": 999},
]

def get_plan(pid):
    for p in PLANS:
        if p["id"] == pid:
            return p
    return None

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_admin(user) -> bool:
    return user.id in ADMIN_IDS

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
    """Record a successful payment in MongoDB (idempotent on ref_id).
    Returns True if a new record was inserted, False if already recorded."""
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

async def safe_edit(query, context, text, keyboard, parse_mode=ParseMode.HTML):
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

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    keyboard = [
        [InlineKeyboardButton(u("Our Premium Subscription"),       callback_data="menu_plans")],
        [InlineKeyboardButton(u("Your Paid Subscriptions"),        callback_data="menu_mysubs")],
        [InlineKeyboardButton(u("Want More Premium/Support Team"), callback_data="menu_support")],
        [InlineKeyboardButton(u("Bot Developer/Creator") + " ↗",  callback_data="menu_dev")],
    ]
    msg = (
        f"{b('Hello Members Welcome To The Premium Channel Subscription Bot')} 🖥\n\n"
        f"{b('Here You Can Subscribe To Premium Channels And Access Exclusive Content Without Any Delay')}\n\n"
        f"{b('Make Payment And Get Your Premium Link Right Now In Seconds')}\n\n"
        f"{b('Please Select The Premium You Want To Buy')} 👇"
    )
    rm = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(msg, reply_markup=rm, parse_mode=ParseMode.HTML)
    else:
        await safe_edit(update.callback_query, context, msg, keyboard)

# ── /stats (admin) ────────────────────────────────────────────────────────────
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    total_users    = users_col.count_documents({})
    total_payments = pays_col.count_documents({})
    total_revenue  = list(pays_col.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]))
    revenue = total_revenue[0]["total"] if total_revenue else 0

    # Payments breakdown by plan
    breakdown = list(pays_col.aggregate([
        {"$group": {"_id": "$plan_name", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}},
        {"$sort": {"count": -1}},
    ]))
    lines = "\n".join(
        f"  • {b(r['_id'])}: {r['count']} {u('sales')} (₹{r['amount']})"
        for r in breakdown
    )
    msg = (
        f"📊 {b('Bot Statistics')}\n\n"
        f"👥 {b('Total Users')}: {total_users}\n"
        f"💰 {b('Total Payments')}: {total_payments}\n"
        f"💵 {b('Total Revenue')}: ₹{revenue}\n\n"
        f"📦 {b('Sales by Plan')}:\n{lines or b('No sales yet')}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ── /broadcast (admin) ────────────────────────────────────────────────────────
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            f"{b('Usage')}: {u('Reply to any message/file with /broadcast')}",
            parse_mode=ParseMode.HTML
        )
        return
    src = update.message.reply_to_message
    pending_broadcasts[update.effective_user.id] = {
        "chat_id":    src.chat_id,
        "message_id": src.message_id,
    }
    keyboard = [
        [
            InlineKeyboardButton(u("✅ Confirm"),  callback_data="bc_confirm"),
            InlineKeyboardButton(u("❌ Cancel"),   callback_data="bc_cancel"),
        ]
    ]
    # Preview what will be sent
    preview = (src.caption or src.text or u("(media/file)"))[:200]
    await update.message.reply_text(
        f"📢 {b('Broadcast Confirmation')}\n\n"
        f"{b('Preview')}:\n{preview}\n\n"
        f"{b('This will be sent to ALL')} {users_col.count_documents({})} {b('users.')}\n"
        f"{b('Forward tag will be removed. Buttons (if any) will be kept.')}\n\n"
        f"{b('Are you sure?')}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def bc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user):
        return
    info = pending_broadcasts.pop(query.from_user.id, None)
    if not info:
        await query.edit_message_text(b("No pending broadcast found."), parse_mode=ParseMode.HTML)
        return

    all_users = list(users_col.find({}, {"user_id": 1}))
    success, fail = 0, 0
    status_msg = await query.edit_message_text(
        f"📤 {b('Broadcasting...')} 0/{len(all_users)}",
        parse_mode=ParseMode.HTML,
    )
    for i, usr in enumerate(all_users):
        try:
            await context.bot.copy_message(
                chat_id=usr["user_id"],
                from_chat_id=info["chat_id"],
                message_id=info["message_id"],
                # copy_message strips forward origin automatically
            )
            success += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {usr['user_id']}: {e}")
            fail += 1
        # Update progress every 20 users
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"📤 {b('Broadcasting...')} {i+1}/{len(all_users)}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ {b('Broadcast Complete!')}\n\n"
        f"✔️ {b('Sent')}: {success}\n"
        f"❌ {b('Failed')}: {fail}",
        parse_mode=ParseMode.HTML,
    )

async def bc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending_broadcasts.pop(query.from_user.id, None)
    await query.edit_message_text(
        f"❌ {b('Broadcast cancelled.')}",
        parse_mode=ParseMode.HTML,
    )

# ── /check user_id amount (admin) ─────────────────────────────────────────────
async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f"{b('Usage')}: /check {u('user_id amount')}\n"
            f"{u('Example')}: /check 123456789 199",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        target_uid = int(args[0])
        amount_inp = int(args[1])
    except ValueError:
        await update.message.reply_text(b("Invalid user_id or amount."), parse_mode=ParseMode.HTML)
        return

    # 1. Check MongoDB records
    mongo_pays = list(pays_col.find(
        {"user_id": target_uid, "amount": amount_inp},
        {"_id": 0, "plan_name": 1, "paid_at": 1, "ref_id": 1, "pay_type": 1}
    ))

    # 2. Check Razorpay API for payment links matching this user+amount
    rzp_found = []
    try:
        # Fetch payment links and filter by notes
        pl_resp = razorpay_client.payment_link.all({
            "amount": amount_inp * 100,
        })
        for item in (pl_resp.get("items") or []):
            notes = item.get("notes") or {}
            if str(notes.get("user_id", "")) == str(target_uid):
                rzp_found.append({
                    "id":     item.get("id"),
                    "status": item.get("status"),
                    "amount": item.get("amount", 0) // 100,
                })
    except Exception as e:
        logger.warning(f"/check Razorpay error: {e}")

    # 3. Get user info
    user_doc = users_col.find_one({"user_id": target_uid}, {"_id": 0})

    lines = [f"🔍 {b('Payment Check')}\n"]
    lines.append(f"{b('User ID')}: {target_uid}")
    if user_doc:
        name = f"{user_doc.get('first_name','')} {user_doc.get('last_name','') or ''}".strip()
        lines.append(f"{b('Name')}: {name}")
        un = user_doc.get("username")
        if un:
            lines.append(f"{b('Username')}: @{un}")
    lines.append(f"{b('Amount Queried')}: ₹{amount_inp}\n")

    if mongo_pays:
        lines.append(f"✅ {b('MongoDB Records')}: {len(mongo_pays)} {u('payment(s) found')}")
        for p in mongo_pays:
            dt = p['paid_at'].strftime("%d %b %Y %H:%M") if p.get('paid_at') else "N/A"
            lines.append(f"  • {p['plan_name']} | {p['pay_type']} | {dt}")
    else:
        lines.append(f"❌ {b('MongoDB')}: {u('No records found')}")

    lines.append("")
    if rzp_found:
        lines.append(f"✅ {b('Razorpay Records')}: {len(rzp_found)} {u('link(s) found')}")
        for r in rzp_found:
            lines.append(f"  • {r['id']} | {u('Status')}: {r['status']} | ₹{r['amount']}")
    else:
        lines.append(f"❌ {b('Razorpay')}: {u('No matching payment links found')}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

# ── Menu handlers ─────────────────────────────────────────────────────────────
async def menu_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_user(query.from_user)
    keyboard = [[InlineKeyboardButton(u(p["channel"]), callback_data=f"showplan_{p['id']}")] for p in PLANS]
    keyboard.append([InlineKeyboardButton(u("🔙 Back"), callback_data="back_main")])
    msg = f"📦 {b('Available Premium Channels')}\n\n{b('Select A Channel To View Subscription Plans')} 👇"
    await safe_edit(query, context, msg, keyboard)

async def show_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("showplan_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found. Please go back and try again."),
                        [[InlineKeyboardButton(u("🔙 Back"), callback_data="menu_plans")]])
        return
    keyboard = [
        [
            InlineKeyboardButton(u("👁 View Sample Content"), callback_data=f"sample_{pid}"),
            InlineKeyboardButton(u("📸 Payment Proof"),       url=PREMIUM_CHANNEL_LINK),
        ],
        [InlineKeyboardButton(f"₹{plan['price']} - " + u("Permanent"), callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data="menu_plans")],
    ]
    msg = (
        f"📺 {b(plan['channel'])}\n"
        f"{b('Category')}: {b(plan['category'])}\n\n"
        f"{b('Available Plans')} 👇\n"
        f"• {b('Permanent')}: ₹{plan['price']}\n\n"
        f"{b('Select A Plan To Subscribe Or Click View Sample Content To See A Preview')} 🔥"
    )
    await safe_edit(query, context, msg, keyboard)

async def sample_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("sample_"):]
    plan = get_plan(pid)
    keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"showplan_{pid}")]]
    msg = (
        f"🎬 {b('Sample Content Preview')}\n\n"
        f"{b('Channel')}: {b(plan['channel']) if plan else ''}\n\n"
        f"{b('This Is A Premium Channel. Subscribe To Get Full Access To Exclusive Content.')}\n\n"
        f"{b('Contact Admin To Get A Sample')}: @{ADMIN_USERNAME}"
    )
    await safe_edit(query, context, msg, keyboard)

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("buy_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return
    keyboard = [
        [InlineKeyboardButton(u("💳 Pay with Razorpay"), callback_data=f"rzp_{pid}")],
        [InlineKeyboardButton(u("📱 Pay with QR"),        callback_data=f"qr_{pid}")],
        [InlineKeyboardButton(u("🔙 Back"),              callback_data=f"showplan_{pid}")],
    ]
    msg = (
        f"{b('Choose your payment method')}:\n\n"
        f"{b('Channel')}: {b(plan['channel'])}\n"
        f"{b('Plan')}: {b('Permanent')}\n"
        f"{b('Amount')}: ₹{plan['price']}"
    )
    await safe_edit(query, context, msg, keyboard)

async def pay_razorpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("rzp_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return
    try:
        pl = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Subscription: {plan['channel']}",
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"plan_id": pid, "user_id": str(query.from_user.id)},
        })
        short_url = pl.get("short_url", "")
        link_id   = pl.get("id", "")
        pending_payments[query.from_user.id] = {
            "pid": pid, "type": "link", "ref_id": link_id,
            "amount": plan["price"], "timestamp": time.time(),
        }
        keyboard = [
            [InlineKeyboardButton(u("💳 Open Payment Page"), url=short_url)],
            [InlineKeyboardButton(u("✅ I Have Paid"),        callback_data=f"paid_{pid}_link_{link_id}")],
            [InlineKeyboardButton(u("❌ Cancel"),            callback_data=f"showplan_{pid}")],
        ]
        msg = (
            f"💳 {b('Razorpay Payment')}\n\n"
            f"{b('Channel')}: {b(plan['channel'])}\n"
            f"{b('Plan')}: {b('Permanent')}\n"
            f"{b('Amount')}: ₹{plan['price']}\n\n"
            f"{b('Click The Button Below To Open The Payment Page')}\n"
            f"{b('Once Paid, Click I Have Paid Button')}"
        )
        await safe_edit(query, context, msg, keyboard)
    except Exception as e:
        logger.error(f"Razorpay link error: {e}")
        keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{pid}")]]
        await safe_edit(query, context,
            f"❌ {b('Error creating payment. Please try again or contact support.')}\n@{ADMIN_USERNAME}",
            keyboard)

async def pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(u("Generating QR Code..."))
    pid  = query.data[len("qr_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return

    # ── Step 1: generate everything BEFORE touching the current message ────────
    buf    = None
    qr_id  = ""
    gen_ok = False
    try:
        from PIL import Image as PilImage
        qr_resp = razorpay_client.qrcode.create({
            "type": "upi_qr",
            "name": "Premium Subscription",
            "usage": "single_use",
            "fixed_amount": True,
            "payment_amount": plan["price"] * 100,
            "description": f"Subscription: {plan['channel']}",
            "close_by": int(time.time()) + 900,
        })
        qr_id     = qr_resp.get("id", "")
        image_url = qr_resp.get("image_url", "")

        with urllib.request.urlopen(image_url) as resp:
            img_bytes = resp.read()
        full_img = PilImage.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = full_img.size
        crop = full_img.crop((
            int(w * 0.08),
            int(h * 0.30),
            int(w * 0.92),
            int(h * 0.67),
        ))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        buf.seek(0)
        gen_ok = True
    except Exception as e:
        logger.error(f"QR generation failed: {e}")

    # ── Step 2a: generation succeeded — delete old msg and send QR photo ──────
    if gen_ok and buf:
        pending_payments[query.from_user.id] = {
            "pid": pid, "type": "qr", "ref_id": qr_id,
            "amount": plan["price"], "timestamp": time.time(),
        }
        keyboard = [
            [InlineKeyboardButton(u("✅ I've Completed Payment"), callback_data=f"paid_{pid}_qr_{qr_id}")],
            [InlineKeyboardButton(u("❌ Cancel"),                 callback_data=f"showplan_{pid}")],
        ]
        caption = (
            f"📱 {b('Upi Payment Information')}\n\n"
            f"{b('Channel')}: {b(plan['channel'])}\n"
            f"{b('Plan')}: {b('Permanent')}\n"
            f"{b('Amount')}: ₹{plan['price']}\n\n"
            f"📲 {b('Scan The QR Code Above Using Any UPI App')}\n"
            f"{b('Once Paid, Tap I ve Completed Payment')} ✅ {b('Below')}\n\n"
            f"⚠️ {b('If You Are Not Able To Pay In This QR Code Please Try With Paytm, PhonePay Or Any Other Upi App, You May Face Issue With Google Pay App')}\n\n"
            f"⏳ {b('This QR Will Expire In 15 Minutes')}"
        )
        chat_id = query.message.chat_id
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_photo(
            chat_id=chat_id, photo=buf, caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )

    # ── Step 2b: generation failed — restore the payment method selection screen
    else:
        await buy_plan(update, context)

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rest   = query.data[len("paid_"):]
    parts  = rest.split("_", 2)
    pid    = parts[0]
    ptype  = parts[1] if len(parts) > 1 else "link"
    ref_id = parts[2] if len(parts) > 2 else ""
    plan   = get_plan(pid)

    await safe_edit(query, context, f"🔄 {b('Checking Payment...')}", [])
    try:
        # Only use the server-side pending entry for this user — never trust callback data
        # for ref_id, as that would allow replay attacks with previously paid references.
        pending = pending_payments.get(query.from_user.id)
        if not pending:
            raise ValueError("no_pending")

        stored_ref  = pending.get("ref_id", "")
        stored_type = pending.get("type", "link")
        stored_pid  = pending.get("pid", "")

        # Reject if the callback's plan doesn't match the server-side pending plan
        if stored_pid and stored_pid != pid:
            raise ValueError("plan_mismatch")

        if not stored_ref:
            raise ValueError("no_ref")

        verified = False
        if stored_type == "link":
            details = razorpay_client.payment_link.fetch(stored_ref)
            if details.get("status") == "paid":
                verified = True
        elif stored_type == "qr":
            payments = razorpay_client.qrcode.fetch_all_payments(stored_ref)
            for item in (payments.get("items") or []):
                if item.get("status") == "captured":
                    verified = True
                    break

        if verified and plan:
            # Consume the pending entry before recording to prevent double-grant
            pending_payments.pop(query.from_user.id, None)
            newly_inserted = record_payment(query.from_user.id, plan, stored_ref, stored_type)
            if not newly_inserted:
                # ref_id already consumed by another account — deny access
                raise ValueError("already_recorded")
            keyboard = [
                [InlineKeyboardButton(u("🔓 Join Premium Channel"), url=PREMIUM_CHANNEL_LINK)],
                [InlineKeyboardButton(u("🏠 Back to Main Menu"),    callback_data="back_main")],
            ]
            msg = (
                f"✅ {b('Payment Verified Successfully!')}\n\n"
                f"🎉 {b('Welcome To')} {b(plan['channel'])}!\n\n"
                f"🔑 {b('Token Timeout')}: 1 {b('days')}\n\n"
                f"{b('Click The Button Below To Join Your Premium Channel')} 👇\n\n"
                f"{b('If You Face Any Issue Contact')}: @{ADMIN_USERNAME}\n\n"
                f"{b('Thank you for your purchase!')}"
            )
            await safe_edit(query, context, msg, keyboard)
        else:
            raise ValueError("not_verified")
    except Exception as e:
        logger.warning(f"Payment check: {e}")
        keyboard = [
            [InlineKeyboardButton(u("🔄 Try Again Later"),   callback_data=f"paid_{pid}_{ptype}_{ref_id}")],
            [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
        ]
        msg = (
            f"❌ {b('Error Checking Payment')}\n\n"
            f"{b('We Couldn t Verify Your Payment At This Time')}\n"
            f"{b('This Could Be Due To A Delay In The Payment System')}\n\n"
            f"{b('Please Try Again In A Few Minutes Or Contact Support')} @{ADMIN_USERNAME}"
        )
        await safe_edit(query, context, msg, keyboard)

async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    pays  = list(pays_col.find({"user_id": uid}, {"_id": 0, "plan_name": 1, "amount": 1, "paid_at": 1}))
    keyboard = [[InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")]]
    if pays:
        lines = "\n".join(
            f"• {p['plan_name']} — ₹{p['amount']} ({p['paid_at'].strftime('%d %b %Y') if p.get('paid_at') else 'N/A'})"
            for p in pays
        )
        msg = f"📋 {b('Your Paid Subscriptions')}\n\n{lines}"
    else:
        msg = (
            f"📋 {b('Your Paid Subscriptions')}\n\n"
            f"{b('You Don t Have Any Active Subscriptions At The Moment')}\n\n"
            f"{b('To Subscribe To Premium Channels, Go Back And Select Premium Subscription')} ❤️"
        )
    await safe_edit(query, context, msg, keyboard)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("📩 Contact Admin"),     url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
    ]
    msg = (
        f"🆘 {b('Help & Support')}\n\n"
        f"{b('If You Have Any Questions Or Need Assistance With Your Subscription, Please Contact Our Admin')}\n\n"
        f"{b('For Common Questions')}:\n"
        f"- {b('To Subscribe')}: {b('Select Our Premium Subscription From The Main Menu')}\n"
        f"- {b('To Check Your Subscriptions')}: {b('Select My Paid Subscriptions From The Main Menu')}\n"
        f"- {b('Payment Issues')}: {b('Contact Our Admin Directly')}\n"
        f"- {b('Access Problems')}: {b('Contact Our Admin With Your Subscription Details')}\n\n"
        f"{b('Our Support Admin')}: @{ADMIN_USERNAME}"
    )
    await safe_edit(query, context, msg, keyboard)

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("👨‍💻 Contact Developer"), url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
    ]
    msg = (
        f"👨‍💻 {b('Bot Developer/Creator')}\n\n"
        f"{b('This Bot Was Developed By')}: @{ADMIN_USERNAME}\n\n"
        f"{b('For Bot Related Queries Or Custom Bot Development Contact The Developer')}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Callback router ───────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if   data == "menu_plans":         await menu_plans(update, context)
    elif data == "menu_mysubs":        await my_subscriptions(update, context)
    elif data == "menu_support":       await support(update, context)
    elif data == "menu_dev":           await developer(update, context)
    elif data == "back_main":          await start(update, context)
    elif data == "bc_confirm":         await bc_confirm(update, context)
    elif data == "bc_cancel":          await bc_cancel(update, context)
    elif data.startswith("showplan_"): await show_plan(update, context)
    elif data.startswith("sample_"):   await sample_content(update, context)
    elif data.startswith("buy_"):      await buy_plan(update, context)
    elif data.startswith("rzp_"):      await pay_razorpay(update, context)
    elif data.startswith("qr_"):       await pay_qr(update, context)
    elif data.startswith("paid_"):     await i_have_paid(update, context)

# ── Main ──────────────────────────────────────────────────────────────────────
import asyncio

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("check",     cmd_check))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Bot starting with MongoDB + broadcast + stats + check...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
