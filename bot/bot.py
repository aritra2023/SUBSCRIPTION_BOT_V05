import os
import logging
import razorpay
import qrcode
import io
import json
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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

PLANS = [
    {"id": "plan_hawt", "channel": "Plan 1 - HAWT PACK", "category": "SNAP PRIME", "price": 199, "duration_days": 30},
    {"id": "plan_desi", "channel": "Plan 2 - DESI PACK", "category": "SNAP PRIME", "price": 299, "duration_days": 30},
    {"id": "plan_snap", "channel": "Plan 3 - OG SNAP PACK", "category": "SNAP PRIME", "price": 399, "duration_days": 30},
    {"id": "plan_rare", "channel": "Plan 4 - RARE IRL AND EPIC 2 IN 1", "category": "EPIC PRIME", "price": 499, "duration_days": 30},
    {"id": "plan_combo", "channel": "Plan 5 - Combo All Plans", "category": "MEGA PRIME", "price": 699, "duration_days": 30},
    {"id": "plan_famp", "channel": "Plan 6 - FAMP EXCLUSIVE", "category": "FAMP PRIME", "price": 999, "duration_days": 30},
]

pending_payments = {}

def get_plan_by_id(plan_id):
    for p in PLANS:
        if p["id"] == plan_id:
            return p
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(u("Our Premium Subscription"), callback_data="menu_plans")],
        [InlineKeyboardButton(u("Your Paid Subscriptions"), callback_data="menu_my_subs")],
        [InlineKeyboardButton(u("Want More Premium/Support Team"), callback_data="menu_support")],
        [InlineKeyboardButton(u("Bot Developer/Creator") + " ↗", callback_data="menu_dev")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"{u('Hello Members Welcome To The Premium Channel Subscription Bot')} 🖥\n\n"
        f"{u('Here You Can Subscribe To Premium Channels And Access Exclusive Content Without Any Delay')}\n\n"
        f"{u('Make Payment And Get Your Premium Link Right Now In Seconds')}\n\n"
        f"{u('Please Select The Premium You Want To Buy')} 👇"
    )
    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)

async def menu_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(u(p["channel"]), callback_data=f"plan_{p['id']}")] for p in PLANS]
    keyboard.append([InlineKeyboardButton(u("🔙 Back"), callback_data="back_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"📦 {u('Available Premium Channels')}\n\n"
        f"{u('Select A Channel To View Subscription Plans')} 👇"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def show_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = query.data.replace("plan_", "")
    plan = get_plan_by_id(plan_id)
    if not plan:
        await query.edit_message_text(u("Plan not found."))
        return
    keyboard = [
        [InlineKeyboardButton(u("👁 View Sample Content"), callback_data=f"sample_{plan_id}")],
        [InlineKeyboardButton(f"₹{plan['price']} - {u('Permanent')}", callback_data=f"buy_{plan_id}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data="menu_plans")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"📺 {u(plan['channel'])}\n"
        f"{u('Category')}: {u(plan['category'])}\n\n"
        f"{u('Available Plans')} 👇\n"
        f"• {u('Permanent')}: ₹{plan['price']}\n\n"
        f"{u('Select A Plan To Subscribe Or Click View Sample Content To See A Preview')} 🔥"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def sample_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = query.data.replace("sample_", "")
    plan = get_plan_by_id(plan_id)
    keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"plan_{plan_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"🎬 {u('Sample Content Preview')}\n\n"
        f"{u('Channel')}: {u(plan['channel'])}\n\n"
        f"{u('This Is A Premium Channel. Subscribe To Get Full Access To Exclusive Content.')}\n\n"
        f"{u('Contact Admin To Get A Sample')}: {ADMIN_USERNAME}"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = query.data.replace("buy_", "")
    plan = get_plan_by_id(plan_id)
    if not plan:
        await query.edit_message_text(u("Plan not found."))
        return
    keyboard = [
        [InlineKeyboardButton(u("💳 Pay with Razorpay"), callback_data=f"pay_rzp_{plan_id}")],
        [InlineKeyboardButton(u("📱 Pay with QR"), callback_data=f"pay_qr_{plan_id}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data=f"plan_{plan_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"{u('Choose your payment method')}:\n\n"
        f"{u('Channel')}: {u(plan['channel'])}\n"
        f"{u('Plan')}: {u('Permanent')}\n"
        f"{u('Amount')}: ₹{plan['price']}"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def pay_razorpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = query.data.replace("pay_rzp_", "")
    plan = get_plan_by_id(plan_id)
    if not plan:
        await query.edit_message_text(u("Plan not found."))
        return
    try:
        order = razorpay_client.order.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "plan_id": plan_id,
                "user_id": str(query.from_user.id),
                "plan_name": plan["channel"],
            }
        })
        order_id = order["id"]
        payment_link_data = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Subscription: {plan['channel']}",
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"plan_id": plan_id, "user_id": str(query.from_user.id)},
            "callback_url": "",
            "callback_method": "get",
        })
        short_url = payment_link_data.get("short_url", "")
        link_id = payment_link_data.get("id", "")
        pending_payments[query.from_user.id] = {
            "plan_id": plan_id,
            "order_id": order_id,
            "link_id": link_id,
            "amount": plan["price"],
            "timestamp": time.time(),
        }
        keyboard = [
            [InlineKeyboardButton(u("💳 Open Payment Page"), url=short_url)],
            [InlineKeyboardButton(u("✅ I Have Paid"), callback_data=f"paid_{plan_id}_{link_id}")],
            [InlineKeyboardButton(u("❌ Cancel"), callback_data=f"plan_{plan_id}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = (
            f"💳 {u('Razorpay Payment')}\n\n"
            f"{u('Channel')}: {u(plan['channel'])}\n"
            f"{u('Plan')}: {u('Permanent')}\n"
            f"{u('Amount')}: ₹{plan['price']}\n\n"
            f"{u('Click The Button Below To Open The Payment Page')}\n"
            f"{u('Once Paid Click I Have Paid Button')}"
        )
        await query.edit_message_text(msg, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Razorpay error: {e}")
        keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{plan_id}")]]
        await query.edit_message_text(
            f"❌ {u('Error creating payment. Please try again or contact support.')}\n{ADMIN_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(u("Generating QR Code..."))
    plan_id = query.data.replace("pay_qr_", "")
    plan = get_plan_by_id(plan_id)
    if not plan:
        await query.edit_message_text(u("Plan not found."))
        return
    try:
        order = razorpay_client.order.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "plan_id": plan_id,
                "user_id": str(query.from_user.id),
                "plan_name": plan["channel"],
            }
        })
        order_id = order["id"]
        payment_link_data = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Subscription: {plan['channel']}",
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"plan_id": plan_id, "user_id": str(query.from_user.id)},
            "callback_url": "",
            "callback_method": "get",
        })
        short_url = payment_link_data.get("short_url", "")
        link_id = payment_link_data.get("id", "")
        pending_payments[query.from_user.id] = {
            "plan_id": plan_id,
            "order_id": order_id,
            "link_id": link_id,
            "amount": plan["price"],
            "timestamp": time.time(),
        }
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(short_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        keyboard = [
            [InlineKeyboardButton(u("✅ I've Completed Payment"), callback_data=f"paid_{plan_id}_{link_id}")],
            [InlineKeyboardButton(u("❌ Cancel"), callback_data=f"plan_{plan_id}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        caption = (
            f"📱 {u('Upi Payment Information')}\n\n"
            f"{u('Channel')}: {u(plan['channel'])}\n"
            f"{u('Plan')}: {u('Permanent')}\n"
            f"{u('Amount')}: ₹{plan['price']}\n\n"
            f"📲 {u('Scan The QR Code Above Using Any UPI App')}\n"
            f"{u('Once Paid, Tap I ve Completed Payment')} ✅ {u('Below')}\n\n"
            f"⚠️ {u('If You Are Not Able To Pay In This QR Code Please Try With Paytm, PhonePay Or Any Other Upi App, You May Face Issue With Google Pay App')}\n\n"
            f"⏳ {u('This QR Will Expire In 5 Minutes')}"
        )
        await query.message.reply_photo(
            photo=buf,
            caption=caption,
            reply_markup=reply_markup,
        )
        await query.delete_message()
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{plan_id}")]]
        await query.edit_message_text(
            f"❌ {u('Error generating QR. Please try again or contact support.')}\n{ADMIN_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 2)
    plan_id = parts[1]
    link_id = parts[2] if len(parts) > 2 else ""
    plan = get_plan_by_id(plan_id)
    await query.edit_message_text(f"🔄 {u('Checking Payment...')}")
    try:
        verified = False
        if link_id:
            link_details = razorpay_client.payment_link.fetch(link_id)
            status = link_details.get("status", "")
            if status == "paid":
                verified = True
        if not verified:
            pending = pending_payments.get(query.from_user.id, {})
            if pending.get("order_id"):
                payments = razorpay_client.order.payments(pending["order_id"])
                items = payments.get("items", [])
                for item in items:
                    if item.get("status") == "captured":
                        verified = True
                        break
        if verified:
            expiry = datetime.now() + timedelta(days=plan["duration_days"])
            keyboard = [[InlineKeyboardButton(u("🏠 Back to Main Menu"), callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            msg = (
                f"✅ {u('Payment Verified Successfully!')}\n\n"
                f"🎉 {u('Welcome To')} {u(plan['channel'])}!\n\n"
                f"📅 {u('Your subscription is active.')}\n"
                f"{u('Please contact admin to get your premium link')}:\n"
                f"{ADMIN_USERNAME}\n\n"
                f"🔑 {u('Token Timeout')}: 1 {u('days')}\n\n"
                f"{u('Thank you for your purchase!')}"
            )
            await query.edit_message_text(msg, reply_markup=reply_markup)
            pending_payments.pop(query.from_user.id, None)
        else:
            keyboard = [
                [InlineKeyboardButton(u("🔄 Try Again Later"), callback_data=f"paid_{plan_id}_{link_id}")],
                [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            msg = (
                f"❌ {u('Error Checking Payment')}\n\n"
                f"{u('We Couldn t Verify Your Payment At This Time')}\n"
                f"{u('This Could Be Due To A Delay In The Payment System')}\n\n"
                f"{u('Please Try Again In A Few Minutes Or Contact Support')} {ADMIN_USERNAME}"
            )
            await query.edit_message_text(msg, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        keyboard = [
            [InlineKeyboardButton(u("🔄 Try Again Later"), callback_data=f"paid_{plan_id}_{link_id}")],
            [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = (
            f"❌ {u('Error Checking Payment')}\n\n"
            f"{u('We Couldn t Verify Your Payment At This Time')}\n"
            f"{u('This Could Be Due To A Delay In The Payment System')}\n\n"
            f"{u('Please Try Again In A Few Minutes Or Contact Support')} {ADMIN_USERNAME}"
        )
        await query.edit_message_text(msg, reply_markup=reply_markup)

async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"📋 {u('Your Paid Subscriptions')}\n\n"
        f"{u('You Don t Have Any Active Subscriptions At The Moment')}\n\n"
        f"{u('To Subscribe To Premium Channels, Go Back And Select Premium Subscription')} ❤️"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("📩 Contact Admin"), url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"🆘 {u('Help & Support')}\n\n"
        f"{u('If You Have Any Questions Or Need Assistance With Your Subscription, Please Contact Our Admin')}\n\n"
        f"{u('For Common Questions')}:\n"
        f"- {u('To Subscribe')}: {u('Select Our Premium Subscription From The Main Menu')}\n"
        f"- {u('To Check Your Subscriptions')}: {u('Select My Paid Subscriptions From The Main Menu')}\n"
        f"- {u('Payment Issues')}: {u('Contact Our Admin Directly')}\n"
        f"- {u('Access Problems')}: {u('Contact Our Admin With Your Subscription Details')}\n"
        f"- {u('If You Need More Premium Then Talk To Our Support Admin')}\n\n"
        f"{u('Our Support Admin')}: {ADMIN_USERNAME}"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("👨‍💻 Contact Developer"), url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"👨‍💻 {u('Bot Developer/Creator')}\n\n"
        f"{u('This Bot Was Developed By')}: {ADMIN_USERNAME}\n\n"
        f"{u('For Bot Related Queries Or Custom Bot Development Contact The Developer')}"
    )
    await query.edit_message_text(msg, reply_markup=reply_markup)

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "menu_plans":
        await menu_plans(update, context)
    elif data == "menu_my_subs":
        await my_subscriptions(update, context)
    elif data == "menu_support":
        await support(update, context)
    elif data == "menu_dev":
        await developer(update, context)
    elif data == "back_main":
        await back_main(update, context)
    elif data.startswith("plan_"):
        await show_plan(update, context)
    elif data.startswith("sample_"):
        await sample_content(update, context)
    elif data.startswith("buy_"):
        await buy_plan(update, context)
    elif data.startswith("pay_rzp_"):
        await pay_razorpay(update, context)
    elif data.startswith("pay_qr_"):
        await pay_qr(update, context)
    elif data.startswith("paid_"):
        await i_have_paid(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
