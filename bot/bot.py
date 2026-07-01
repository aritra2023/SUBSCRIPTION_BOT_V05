import os
import logging
import razorpay
import io
import time
import urllib.request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RAZORPAY_KEY_ID = os.environ["RAZORPAY_KEY_ID"]
RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]
ADMIN_USERNAME = "@aritramahatma"
PREMIUM_CHANNEL_LINK = "https://t.me/+K2hQ7Cdgm1Y3MjY1"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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

PLANS = [
    {"id": "hawt",  "channel": "Plan 1 - HAWT PACK",               "category": "SNAP PRIME", "price": 199},
    {"id": "desi",  "channel": "Plan 2 - DESI PACK",               "category": "SNAP PRIME", "price": 299},
    {"id": "snap",  "channel": "Plan 3 - OG SNAP PACK",            "category": "SNAP PRIME", "price": 399},
    {"id": "rare",  "channel": "Plan 4 - RARE IRL AND EPIC 2 IN 1","category": "EPIC PRIME", "price": 499},
    {"id": "combo", "channel": "Plan 5 - Combo All Plans",          "category": "MEGA PRIME", "price": 699},
    {"id": "famp",  "channel": "Plan 6 - FAMP EXCLUSIVE",           "category": "FAMP PRIME", "price": 999},
]

pending_payments = {}

def get_plan(pid):
    for p in PLANS:
        if p["id"] == pid:
            return p
    return None

# ── Smart edit: works whether the current message is text OR a photo ──────────
async def safe_edit(query, context, text, keyboard, parse_mode=ParseMode.HTML):
    rm = InlineKeyboardMarkup(keyboard)
    try:
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text, reply_markup=rm, parse_mode=parse_mode,
            )
        else:
            await query.edit_message_text(text, reply_markup=rm, parse_mode=parse_mode)
    except Exception as e:
        logger.warning(f"safe_edit fallback: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text, reply_markup=rm, parse_mode=parse_mode,
        )

# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def menu_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
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
        await safe_edit(query, context, b("Plan not found. Please go back and try again."), [[InlineKeyboardButton(u("🔙 Back"), callback_data="menu_plans")]])
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
        f"{b('Contact Admin To Get A Sample')}: {ADMIN_USERNAME}"
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
            f"❌ {b('Error creating payment. Please try again or contact support.')}\n{ADMIN_USERNAME}",
            keyboard)

async def pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(u("Generating QR Code..."))
    pid  = query.data[len("qr_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return
    try:
        # Use Razorpay QR Code API — generates a real UPI QR (scan → pay directly in any UPI app)
        qr_resp = razorpay_client.qrcode.create({
            "type": "upi_qr",
            "name": "Premium Subscription",
            "usage": "single_use",
            "fixed_amount": True,
            "payment_amount": plan["price"] * 100,
            "description": f"Subscription: {plan['channel']}",
            "close_by": int(time.time()) + 900,  # expires in 15 min
        })
        qr_id     = qr_resp.get("id", "")
        image_url = qr_resp.get("image_url", "")

        # Download the QR image Razorpay generated
        with urllib.request.urlopen(image_url) as resp:
            img_bytes = resp.read()
        buf = io.BytesIO(img_bytes)
        buf.seek(0)

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
        # Delete old message, send photo
        chat_id = query.message.chat_id
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=buf,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"QR error: {e}")
        keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{pid}")]]
        await safe_edit(query, context,
            f"❌ {b('Error generating QR. Please try again or contact support.')}\n{ADMIN_USERNAME}",
            keyboard)

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Format: paid_{pid}_{type}_{ref_id}
    # type = "link" or "qr"
    rest   = query.data[len("paid_"):]
    parts  = rest.split("_", 2)   # [pid, type, ref_id]
    pid    = parts[0]
    ptype  = parts[1] if len(parts) > 1 else "link"
    ref_id = parts[2] if len(parts) > 2 else ""
    plan   = get_plan(pid)

    await safe_edit(query, context, f"🔄 {b('Checking Payment...')}", [])
    try:
        verified = False

        if ptype == "link" and ref_id:
            details = razorpay_client.payment_link.fetch(ref_id)
            if details.get("status") == "paid":
                verified = True

        elif ptype == "qr" and ref_id:
            payments = razorpay_client.qrcode.fetch_all_payments(ref_id)
            items = payments.get("items", [])
            for item in items:
                if item.get("status") == "captured":
                    verified = True
                    break

        # Fallback: check stored pending
        if not verified:
            pending = pending_payments.get(query.from_user.id, {})
            stored_ref = pending.get("ref_id", "")
            stored_type = pending.get("type", "link")
            if stored_ref:
                if stored_type == "link":
                    d = razorpay_client.payment_link.fetch(stored_ref)
                    if d.get("status") == "paid":
                        verified = True
                elif stored_type == "qr":
                    p = razorpay_client.qrcode.fetch_all_payments(stored_ref)
                    for item in p.get("items", []):
                        if item.get("status") == "captured":
                            verified = True
                            break

        if verified:
            pending_payments.pop(query.from_user.id, None)
            keyboard = [
                [InlineKeyboardButton(u("🔓 Join Premium Channel"), url=PREMIUM_CHANNEL_LINK)],
                [InlineKeyboardButton(u("🏠 Back to Main Menu"),    callback_data="back_main")],
            ]
            msg = (
                f"✅ {b('Payment Verified Successfully!')}\n\n"
                f"🎉 {b('Welcome To')} {b(plan['channel']) if plan else ''}!\n\n"
                f"🔑 {b('Token Timeout')}: 1 {b('days')}\n\n"
                f"{b('Click The Button Below To Join Your Premium Channel')} 👇\n\n"
                f"{b('If You Face Any Issue Contact')}: {ADMIN_USERNAME}\n\n"
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
            f"{b('Please Try Again In A Few Minutes Or Contact Support')} {ADMIN_USERNAME}"
        )
        await safe_edit(query, context, msg, keyboard)

async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")]]
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
        [InlineKeyboardButton(u("📩 Contact Admin"),     url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
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
        f"{b('Our Support Admin')}: {ADMIN_USERNAME}"
    )
    await safe_edit(query, context, msg, keyboard)

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("👨‍💻 Contact Developer"), url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
    ]
    msg = (
        f"👨‍💻 {b('Bot Developer/Creator')}\n\n"
        f"{b('This Bot Was Developed By')}: {ADMIN_USERNAME}\n\n"
        f"{b('For Bot Related Queries Or Custom Bot Development Contact The Developer')}"
    )
    await safe_edit(query, context, msg, keyboard)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if   data == "menu_plans":         await menu_plans(update, context)
    elif data == "menu_mysubs":        await my_subscriptions(update, context)
    elif data == "menu_support":       await support(update, context)
    elif data == "menu_dev":           await developer(update, context)
    elif data == "back_main":          await start(update, context)
    elif data.startswith("showplan_"): await show_plan(update, context)
    elif data.startswith("sample_"):   await sample_content(update, context)
    elif data.startswith("buy_"):      await buy_plan(update, context)
    elif data.startswith("rzp_"):      await pay_razorpay(update, context)
    elif data.startswith("qr_"):       await pay_qr(update, context)
    elif data.startswith("paid_"):     await i_have_paid(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
