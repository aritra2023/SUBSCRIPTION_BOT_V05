import os
import logging
import razorpay
import qrcode
import io
import time
from datetime import datetime, timedelta
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

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Unicode small caps converter
def u(text):
    SMALL_CAPS = {
        'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ғ','g':'ɢ','h':'ʜ',
        'i':'ɪ','j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ',
        'q':'Q','r':'ʀ','s':'s','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x',
        'y':'ʏ','z':'ᴢ',
        'A':'A','B':'B','C':'C','D':'D','E':'E','F':'F','G':'G','H':'H',
        'I':'I','J':'J','K':'K','L':'L','M':'M','N':'N','O':'O','P':'P',
        'Q':'Q','R':'R','S':'S','T':'T','U':'U','V':'V','W':'W','X':'X',
        'Y':'Y','Z':'Z',
    }
    return ''.join(SMALL_CAPS.get(c, c) for c in text)

# Bold + small caps helper
def b(text):
    return f"<b>{u(text)}</b>"

# Plans - IDs without "plan_" prefix to avoid parsing issues
PLANS = [
    {"id": "hawt",  "channel": "Plan 1 - HAWT PACK",              "category": "SNAP PRIME",  "price": 199, "duration_days": 30},
    {"id": "desi",  "channel": "Plan 2 - DESI PACK",              "category": "SNAP PRIME",  "price": 299, "duration_days": 30},
    {"id": "snap",  "channel": "Plan 3 - OG SNAP PACK",           "category": "SNAP PRIME",  "price": 399, "duration_days": 30},
    {"id": "rare",  "channel": "Plan 4 - RARE IRL AND EPIC 2 IN 1","category": "EPIC PRIME", "price": 499, "duration_days": 30},
    {"id": "combo", "channel": "Plan 5 - Combo All Plans",         "category": "MEGA PRIME",  "price": 699, "duration_days": 30},
    {"id": "famp",  "channel": "Plan 6 - FAMP EXCLUSIVE",          "category": "FAMP PRIME",  "price": 999, "duration_days": 30},
]

pending_payments = {}

def get_plan(pid):
    for p in PLANS:
        if p["id"] == pid:
            return p
    return None

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
    if update.message:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def menu_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(u(p["channel"]), callback_data=f"showplan_{p['id']}")] for p in PLANS]
    keyboard.append([InlineKeyboardButton(u("🔙 Back"), callback_data="back_main")])
    msg = (
        f"📦 {b('Available Premium Channels')}\n\n"
        f"{b('Select A Channel To View Subscription Plans')} 👇"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def show_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data[len("showplan_"):]
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(f"{b('Plan not found. Please go back and try again.')}", parse_mode=ParseMode.HTML)
        return
    keyboard = [
        [InlineKeyboardButton(u("👁 View Sample Content"),           callback_data=f"sample_{pid}")],
        [InlineKeyboardButton(f"₹{plan['price']} - " + u("Permanent"), callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(u("🔙 Back"),                          callback_data="menu_plans")],
    ]
    msg = (
        f"📺 {b(plan['channel'])}\n"
        f"{b('Category')}: {b(plan['category'])}\n\n"
        f"{b('Available Plans')} 👇\n"
        f"• {b('Permanent')}: ₹{plan['price']}\n\n"
        f"{b('Select A Plan To Subscribe Or Click View Sample Content To See A Preview')} 🔥"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def sample_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data[len("sample_"):]
    plan = get_plan(pid)
    keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"showplan_{pid}")]]
    msg = (
        f"🎬 {b('Sample Content Preview')}\n\n"
        f"{b('Channel')}: {b(plan['channel']) if plan else ''}\n\n"
        f"{b('This Is A Premium Channel. Subscribe To Get Full Access To Exclusive Content.')}\n\n"
        f"{b('Contact Admin To Get A Sample')}: {ADMIN_USERNAME}"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data[len("buy_"):]
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(b("Plan not found."), parse_mode=ParseMode.HTML)
        return
    keyboard = [
        [InlineKeyboardButton(u("💳 Pay with Razorpay"),  callback_data=f"rzp_{pid}")],
        [InlineKeyboardButton(u("📱 Pay with QR"),         callback_data=f"qr_{pid}")],
        [InlineKeyboardButton(u("🔙 Back"),               callback_data=f"showplan_{pid}")],
    ]
    msg = (
        f"{b('Choose your payment method')}:\n\n"
        f"{b('Channel')}: {b(plan['channel'])}\n"
        f"{b('Plan')}: {b('Permanent')}\n"
        f"{b('Amount')}: ₹{plan['price']}"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def pay_razorpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data[len("rzp_"):]
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(b("Plan not found."), parse_mode=ParseMode.HTML)
        return
    try:
        payment_link_data = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Subscription: {plan['channel']}",
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"plan_id": pid, "user_id": str(query.from_user.id)},
        })
        short_url = payment_link_data.get("short_url", "")
        link_id   = payment_link_data.get("id", "")
        pending_payments[query.from_user.id] = {
            "pid": pid, "link_id": link_id,
            "amount": plan["price"], "timestamp": time.time(),
        }
        keyboard = [
            [InlineKeyboardButton(u("💳 Open Payment Page"),    url=short_url)],
            [InlineKeyboardButton(u("✅ I Have Paid"),           callback_data=f"paid_{pid}_{link_id}")],
            [InlineKeyboardButton(u("❌ Cancel"),               callback_data=f"showplan_{pid}")],
        ]
        msg = (
            f"💳 {b('Razorpay Payment')}\n\n"
            f"{b('Channel')}: {b(plan['channel'])}\n"
            f"{b('Plan')}: {b('Permanent')}\n"
            f"{b('Amount')}: ₹{plan['price']}\n\n"
            f"{b('Click The Button Below To Open The Payment Page')}\n"
            f"{b('Once Paid, Click I Have Paid Button')}"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Razorpay error: {e}")
        keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{pid}")]]
        await query.edit_message_text(
            f"❌ {b('Error creating payment. Please try again or contact support.')}\n{ADMIN_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        )

async def pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(u("Generating QR Code..."))
    pid = query.data[len("qr_"):]
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(b("Plan not found."), parse_mode=ParseMode.HTML)
        return
    try:
        payment_link_data = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Subscription: {plan['channel']}",
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"plan_id": pid, "user_id": str(query.from_user.id)},
        })
        short_url = payment_link_data.get("short_url", "")
        link_id   = payment_link_data.get("id", "")
        pending_payments[query.from_user.id] = {
            "pid": pid, "link_id": link_id,
            "amount": plan["price"], "timestamp": time.time(),
        }
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(short_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        keyboard = [
            [InlineKeyboardButton(u("✅ I've Completed Payment"), callback_data=f"paid_{pid}_{link_id}")],
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
            f"⏳ {b('This QR Will Expire In 5 Minutes')}"
        )
        await query.message.reply_photo(photo=buf, caption=caption,
                                         reply_markup=InlineKeyboardMarkup(keyboard),
                                         parse_mode=ParseMode.HTML)
        await query.delete_message()
    except Exception as e:
        logger.error(f"QR error: {e}")
        keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{pid}")]]
        await query.edit_message_text(
            f"❌ {b('Error generating QR. Please try again or contact support.')}\n{ADMIN_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        )

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Format: paid_{pid}_{link_id}
    rest    = query.data[len("paid_"):]
    parts   = rest.split("_", 1)
    pid     = parts[0]
    link_id = parts[1] if len(parts) > 1 else ""
    plan    = get_plan(pid)

    await query.edit_message_text(f"🔄 {b('Checking Payment...')}", parse_mode=ParseMode.HTML)
    try:
        verified = False
        if link_id:
            link_details = razorpay_client.payment_link.fetch(link_id)
            if link_details.get("status") == "paid":
                verified = True
        if not verified:
            pending = pending_payments.get(query.from_user.id, {})
            if pending.get("link_id"):
                ld = razorpay_client.payment_link.fetch(pending["link_id"])
                if ld.get("status") == "paid":
                    verified = True

        if verified:
            keyboard = [[InlineKeyboardButton(u("🏠 Back to Main Menu"), callback_data="back_main")]]
            msg = (
                f"✅ {b('Payment Verified Successfully!')}\n\n"
                f"🎉 {b('Welcome To')} {b(plan['channel']) if plan else ''}!\n\n"
                f"{b('Please contact admin to get your premium link')}:\n"
                f"{ADMIN_USERNAME}\n\n"
                f"🔑 {b('Token Timeout')}: 1 {b('days')}\n\n"
                f"{b('Thank you for your purchase!')}"
            )
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
            pending_payments.pop(query.from_user.id, None)
        else:
            raise ValueError("not_verified")
    except Exception as e:
        keyboard = [
            [InlineKeyboardButton(u("🔄 Try Again Later"),       callback_data=f"paid_{pid}_{link_id}")],
            [InlineKeyboardButton(u("🔙 Back to Main Menu"),     callback_data="back_main")],
        ]
        msg = (
            f"❌ {b('Error Checking Payment')}\n\n"
            f"{b('We Couldn t Verify Your Payment At This Time')}\n"
            f"{b('This Could Be Due To A Delay In The Payment System')}\n\n"
            f"{b('Please Try Again In A Few Minutes Or Contact Support')} {ADMIN_USERNAME}"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")]]
    msg = (
        f"📋 {b('Your Paid Subscriptions')}\n\n"
        f"{b('You Don t Have Any Active Subscriptions At The Moment')}\n\n"
        f"{b('To Subscribe To Premium Channels, Go Back And Select Premium Subscription')} ❤️"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("📩 Contact Admin"),         url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"),     callback_data="back_main")],
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
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("👨‍💻 Contact Developer"),     url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"),     callback_data="back_main")],
    ]
    msg = (
        f"👨‍💻 {b('Bot Developer/Creator')}\n\n"
        f"{b('This Bot Was Developed By')}: {ADMIN_USERNAME}\n\n"
        f"{b('For Bot Related Queries Or Custom Bot Development Contact The Developer')}"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if   data == "menu_plans":    await menu_plans(update, context)
    elif data == "menu_mysubs":   await my_subscriptions(update, context)
    elif data == "menu_support":  await support(update, context)
    elif data == "menu_dev":      await developer(update, context)
    elif data == "back_main":     await start(update, context)
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
