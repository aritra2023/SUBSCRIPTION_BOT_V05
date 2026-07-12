import asyncio
import io
import json
import random
import time
import uuid
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ── Welcome images (randomly shown on /start) ─────────────────────────────────
START_IMAGES = [
    "https://files.catbox.moe/v80oav.jpg",
    "https://files.catbox.moe/zcmytc.jpg",
]

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import (
    ADMIN_USERNAME, ADMIN_IDS, SUPPORT_USERNAME, DEV_USERNAME,
    PREMIUM_CHANNEL_LINK, FREE_CHANNEL_LINK,
    CRYPTO_NETWORK, CRYPTO_ADDRESS,
    razorpay_client, users_col, pays_col, plans_col,
    pending_payments, pending_recharges, pending_broadcasts,
    get_all_plans, get_plan,
    get_free_channel_link, get_tutorial_link, set_setting, remove_setting,
)
from utils import (
    u, b, is_admin, safe_edit, save_user, record_payment,
    get_wallet, credit_wallet, deduct_wallet,
    needs_keyboard_update, mark_keyboard_sent,
)
import logging
logger = logging.getLogger(__name__)

# ── Recharge amount presets ────────────────────────────────────────────────────
RECHARGE_AMOUNTS = [25, 50, 100]

# ── Persistent bottom keyboard ─────────────────────────────────────────────────
BTN_FREE    = "Free Channel ✅"
BTN_REFER   = "Refer and Earn 🎁"

REPLY_KB_TEXTS = {BTN_FREE, BTN_REFER}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [[BTN_FREE, BTN_REFER]],
    resize_keyboard=True,
    is_persistent=True,
)

# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    referred_by = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referred_by = int(arg[4:])
                if referred_by == user.id:
                    referred_by = None
            except ValueError:
                referred_by = None

    is_new = save_user(user, referred_by=referred_by)

    if is_new and referred_by:
        existing_referrer = users_col.find_one({"user_id": referred_by})
        if existing_referrer:
            credit_wallet(referred_by, 1, field="referral_balance")
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🌟 {b('Referral Bonus')}\n\n"
                         f"{b('Someone joined using your referral link.')}\n"
                         f"{b('Rs.1 has been credited to your referral balance.')}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    msg = (
        f"🌟 {b('Hello! Welcome To The Premium Channel Bot')}\n\n"
        f"{b('Subscribe To Premium Channels And Get Exclusive Content Instantly')}\n\n"
        f"💳 {b('Recharge Your Wallet And Get Your Premium Link In Seconds')}\n\n"
        f"👇 {b('Use The Buttons Below To Navigate')}"
    )
    inline = [
        [InlineKeyboardButton(u("🛍️ Available Subscriptions"), callback_data="menu_plans")],
        [
            InlineKeyboardButton(u("👤 About"),          callback_data="menu_about"),
            InlineKeyboardButton(u("💳 Wallet"),         callback_data="menu_wallet"),
        ],
        [
            InlineKeyboardButton(u("🎧 Support"),        callback_data="menu_support"),
            InlineKeyboardButton(u("❓ How to Buy"),     callback_data="menu_howtobuy"),
        ],
    ]
    if update.message:
        # Send keyboard only when the user hasn't received the current version yet
        if needs_keyboard_update(user.id):
            await update.message.reply_text("\u2063", reply_markup=MAIN_KEYBOARD)
            mark_keyboard_sent(user.id)
        await update.message.reply_photo(
            photo=random.choice(START_IMAGES),
            caption=msg,
            reply_markup=InlineKeyboardMarkup(inline),
            parse_mode=ParseMode.HTML,
        )
    else:
        # Called from a callback (e.g. Back button) — delete old message, send fresh photo
        query = update.callback_query
        chat_id = query.message.chat_id
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_photo(
            chat_id=chat_id,
            photo="https://files.catbox.moe/v80oav.jpg",
            caption=msg,
            reply_markup=InlineKeyboardMarkup(inline),
            parse_mode=ParseMode.HTML,
        )

# ── /addbalance user_id amount (admin) ────────────────────────────────────────
async def cmd_addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f"{b('Usage')}: /addbalance {u('user_id amount')}\n"
            f"{u('Example')}: /addbalance 123456789 100",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        target_uid = int(args[0])
        amount     = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            b("❌ Invalid user_id or amount. Amount must be a positive number."),
            parse_mode=ParseMode.HTML,
        )
        return

    user_doc = users_col.find_one({"user_id": target_uid})
    if not user_doc:
        await update.message.reply_text(
            f"❌ {b('User not found.')} {u('Make sure the user has started the bot.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    credit_wallet(target_uid, amount, field="wallet_balance")
    wb, rb = get_wallet(target_uid)

    name = f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '') or ''}".strip()
    un   = f"@{user_doc['username']}" if user_doc.get("username") else u("(no username)")

    await update.message.reply_text(
        f"✅ {b('Balance Added Successfully')}\n\n"
        f"👤 {b('User')}: {name} {un}\n"
        f"🆔 {b('ID')}: <code>{target_uid}</code>\n"
        f"💰 {b('Added')}: Rs.{amount}\n\n"
        f"💳 {b('New Wallet Balance')}: Rs.{wb}\n"
        f"🎁 {b('Referral Balance')}: Rs.{rb}\n"
        f"💵 {b('Total')}: Rs.{wb + rb}",
        parse_mode=ParseMode.HTML,
    )

    # Notify the user
    try:
        await context.bot.send_message(
            chat_id=target_uid,
            text=f"✅ {b('Wallet Credited')}\n\n"
                 f"💰 {b('Rs.'+ str(amount) + ' has been added to your wallet by admin.')}\n\n"
                 f"💳 {b('Recharge Balance')}: Rs.{wb}\n"
                 f"🎁 {b('Referral Balance')}: Rs.{rb}\n"
                 f"💵 {b('Total Balance')}: Rs.{wb + rb}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

# ── /stats (admin) ─────────────────────────────────────────────────────────────
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
    breakdown = list(pays_col.aggregate([
        {"$group": {"_id": "$plan_name", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}},
        {"$sort": {"count": -1}},
    ]))
    lines = "\n".join(
        f"  {b(r['_id'])}: {r['count']} {u('sales')} (Rs.{r['amount']})"
        for r in breakdown
    )
    msg = (
        f"📊 {b('Bot Statistics')}\n\n"
        f"{b('Total Users')}: {total_users}\n"
        f"{b('Total Payments')}: {total_payments}\n"
        f"{b('Total Revenue')}: Rs.{revenue}\n\n"
        f"🌟 {b('Sales by Plan')}:\n{lines or b('No sales yet')}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ── /broadcast (admin) ─────────────────────────────────────────────────────────
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
    keyboard = [[
        InlineKeyboardButton(u("✅ Confirm"), callback_data="bc_confirm"),
        InlineKeyboardButton(u("❌ Cancel"),  callback_data="bc_cancel"),
    ]]
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
        f"📢 {b('Broadcasting...')} 0/{len(all_users)}", parse_mode=ParseMode.HTML,
    )
    for i, usr in enumerate(all_users):
        try:
            await context.bot.copy_message(
                chat_id=usr["user_id"],
                from_chat_id=info["chat_id"],
                message_id=info["message_id"],
            )
            success += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {usr['user_id']}: {e}")
            fail += 1
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 {b('Broadcasting...')} {i+1}/{len(all_users)}", parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(
        f"✅ {b('Broadcast Complete')}\n\n"
        f"✅ {b('Sent')}: {success}\n"
        f"❌ {b('Failed')}: {fail}",
        parse_mode=ParseMode.HTML,
    )

async def bc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending_broadcasts.pop(query.from_user.id, None)
    await query.edit_message_text(f"❌ {b('Broadcast cancelled.')}", parse_mode=ParseMode.HTML)

# ── /check user_id amount (admin) ──────────────────────────────────────────────
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

    mongo_pays = list(pays_col.find(
        {"user_id": target_uid, "amount": amount_inp},
        {"_id": 0, "plan_name": 1, "paid_at": 1, "ref_id": 1, "pay_type": 1}
    ))
    rzp_found = []
    try:
        pl_resp = razorpay_client.payment_link.all({"amount": amount_inp * 100})
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

    user_doc = users_col.find_one({"user_id": target_uid}, {"_id": 0})
    lines = [f"🔍 {b('Payment Check')}\n"]
    lines.append(f"{b('User ID')}: {target_uid}")
    if user_doc:
        name = f"{user_doc.get('first_name','')} {user_doc.get('last_name','') or ''}".strip()
        lines.append(f"{b('Name')}: {name}")
        un = user_doc.get("username")
        if un:
            lines.append(f"{b('Username')}: @{un}")
        lines.append(f"{b('Wallet Balance')}: Rs.{user_doc.get('wallet_balance', 0)}")
        lines.append(f"{b('Referral Balance')}: Rs.{user_doc.get('referral_balance', 0)}")
    lines.append(f"{b('Amount Queried')}: Rs.{amount_inp}\n")
    if mongo_pays:
        lines.append(f"✅ {b('MongoDB Records')}: {len(mongo_pays)} {u('payment(s) found')}")
        for p in mongo_pays:
            dt = p['paid_at'].strftime("%d %b %Y %H:%M") if p.get('paid_at') else "N/A"
            lines.append(f"  {p['plan_name']} | {p['pay_type']} | {dt}")
    else:
        lines.append(f"❌ {b('MongoDB')}: {u('No records found')}")
    lines.append("")
    if rzp_found:
        lines.append(f"✅ {b('Razorpay Records')}: {len(rzp_found)} {u('link(s) found')}")
        for r in rzp_found:
            lines.append(f"  {r['id']} | {u('Status')}: {r['status']} | Rs.{r['amount']}")
    else:
        lines.append(f"❌ {b('Razorpay')}: {u('No matching payment links found')}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

# ── Menu: Available Plans ──────────────────────────────────────────────────────
async def menu_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_user(query.from_user)
    plans = get_all_plans()
    buttons = [InlineKeyboardButton(u(p["channel"]), callback_data=f"showplan_{p['id']}") for p in plans]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton(u("🔙 Back"), callback_data="back_main")])
    msg = f"🌟 {b('Available Premium Channels')}\n\n{b('Select A Channel To View Subscription Plans')} 👇"
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
    sample_link = plan.get("sample_link")
    keyboard = [
        [
            InlineKeyboardButton(u("👁️ View Sample Content"), url=sample_link) if sample_link
            else InlineKeyboardButton(u("👁️ View Sample Content"), callback_data=f"sample_{pid}"),
            InlineKeyboardButton(u("Payment Proof"), url=PREMIUM_CHANNEL_LINK),
        ],
        [InlineKeyboardButton(f"Rs.{plan['price']} - " + u("Permanent"), callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data="menu_plans")],
    ]
    desc = plan.get("description", "")
    msg = (
        f"🌟 {b(plan['channel'])}\n\n"
        f"{desc}\n\n"
        f"{b('Available Plans')} 👇\n"
        f"{b('Permanent')}: Rs.{plan['price']}\n\n"
        f"{b('Select A Plan To Subscribe Or Click View Sample Content To See A Preview')}"
    )
    await safe_edit(query, context, msg, keyboard)

async def sample_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("sample_"):]
    plan = get_plan(pid)
    keyboard = [[InlineKeyboardButton(u("🔙 Back"), callback_data=f"showplan_{pid}")]]
    msg = (
        f"🌟 {b('Sample Content Preview')}\n\n"
        f"{b('Channel')}: {b(plan['channel']) if plan else ''}\n\n"
        f"{b('This Is A Premium Channel. Subscribe To Get Full Access To Exclusive Content.')}\n\n"
        f"{b('Contact Admin To Get A Sample')}: @{SUPPORT_USERNAME}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Buy plan: wallet-based ─────────────────────────────────────────────────────
async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("buy_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return

    wb, rb = get_wallet(query.from_user.id)
    total  = wb + rb
    price  = plan["price"]

    if total >= price:
        keyboard = [
            [InlineKeyboardButton(
                f"✅ {u('Pay')} Rs.{price} {u('from Wallet')}",
                callback_data=f"wpay_{pid}"
            )],
            [InlineKeyboardButton(u("💳 Recharge Wallet"), callback_data="menu_wallet")],
            [InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(u("🔙 Back"), callback_data=f"showplan_{pid}")],
        ]
        msg = (
            f"💳 {b('Pay From Wallet')}\n\n"
            f"{b('Channel')}: {b(plan['channel'])}\n"
            f"{b('Plan')}: {b('Permanent')}\n"
            f"{b('Amount')}: Rs.{price}\n\n"
            f"💳 {b('Your Wallet')}:\n"
            f"  {b('Recharge Balance')}: Rs.{wb}\n"
            f"  {b('Referral Balance')}: Rs.{rb}\n"
            f"  {b('Total')}: Rs.{total}\n\n"
            f"{b('Tap Below To Complete Your Purchase')} 👇"
        )
    else:
        need = price - total
        keyboard = [
            [InlineKeyboardButton(u("💳 Recharge Wallet"), callback_data="menu_wallet")],
            [InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(u("🔙 Back"), callback_data=f"showplan_{pid}")],
        ]
        msg = (
            f"❌ {b('Insufficient Wallet Balance')}\n\n"
            f"{b('Channel')}: {b(plan['channel'])}\n"
            f"{b('Amount Required')}: Rs.{price}\n\n"
            f"💳 {b('Your Wallet')}:\n"
            f"  {b('Recharge Balance')}: Rs.{wb}\n"
            f"  {b('Referral Balance')}: Rs.{rb}\n"
            f"  {b('Total')}: Rs.{total}\n\n"
            f"{b('You Need')} Rs.{need} {b('More To Buy This Plan')}\n"
            f"{b('Please Recharge Your Wallet First')} 👇"
        )

    await safe_edit(query, context, msg, keyboard)

async def wallet_pay_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("wpay_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return

    success = deduct_wallet(query.from_user.id, plan["price"])
    if not success:
        keyboard = [
            [InlineKeyboardButton(u("💳 Recharge Wallet"), callback_data="menu_wallet")],
            [InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{pid}")],
        ]
        await safe_edit(query, context,
            f"❌ {b('Insufficient Balance')}\n\n"
            f"{b('Please Recharge Your Wallet And Try Again.')}",
            keyboard)
        return

    ref_id = f"wallet_{uuid.uuid4().hex[:12]}"
    record_payment(query.from_user.id, plan, ref_id, "wallet")

    keyboard = [
        [InlineKeyboardButton(u("🔑 Join Premium Channel"), url=plan.get("channel_link", PREMIUM_CHANNEL_LINK))],
        [InlineKeyboardButton(u("💬 Support"),              url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Main Menu"),            callback_data="back_main")],
    ]
    wb, rb = get_wallet(query.from_user.id)
    msg = (
        f"✅ {b('Payment Successful')}\n\n"
        f"🌟 {b('Welcome To')} {b(plan['channel'])}\n\n"
        f"Rs.{plan['price']} {b('Deducted From Your Wallet')}\n"
        f"{b('Remaining Balance')}: Rs.{wb + rb}\n\n"
        f"{b('Click The Button Below To Join Your Premium Channel')} 👇\n\n"
        f"{b('If You Face Any Issue Contact')}: @{SUPPORT_USERNAME}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Menu: About ────────────────────────────────────────────────────────────────
async def menu_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    wb, rb = get_wallet(user.id)
    username_str = f"@{user.username}" if user.username else u("Not set")
    keyboard = [[InlineKeyboardButton(u("🔙 Main Menu"), callback_data="back_main")]]
    msg = (
        f"👤 {b('Your Profile')}\n\n"
        f"{b('Telegram ID')}: <code>{user.id}</code>\n"
        f"{b('Username')}: {username_str}\n\n"
        f"🌟 {b('Wallet')}\n"
        f"  {b('Recharge Balance')}: Rs.{wb}\n"
        f"  {b('Referral Balance')}: Rs.{rb}\n"
        f"  {b('Total Balance')}: Rs.{wb + rb}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Menu: Wallet ───────────────────────────────────────────────────────────────
async def menu_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    wb, rb = get_wallet(user.id)
    total = wb + rb

    amt_buttons = [
        InlineKeyboardButton(f"Rs.{amt}", callback_data=f"wamt_{amt}")
        for amt in RECHARGE_AMOUNTS
    ]
    keyboard = [amt_buttons]
    keyboard.append([InlineKeyboardButton(u("✏️ Custom Amount"), callback_data="wamt_custom")])
    keyboard.append([InlineKeyboardButton(u("🔙 Back"), callback_data="back_main")])

    msg = (
        f"💳 {b('Your Wallet')}\n\n"
        f"  {b('Recharge Balance')}: Rs.{wb}\n"
        f"  {b('Referral Balance')}: Rs.{rb}\n"
        f"  {b('Total Balance')}: Rs.{total}\n\n"
        f"💳 {b('Recharge Wallet')}\n"
        f"{b('Select An Amount To Add To Your Wallet')} 👇"
    )
    await safe_edit(query, context, msg, keyboard)

async def wallet_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_recharge"] = True
    keyboard = [[InlineKeyboardButton(u("❌ Cancel"), callback_data="menu_wallet")]]
    await safe_edit(query, context,
        f"✏️ {b('Custom Recharge Amount')}\n\n"
        f"{b('Send The Amount You Want To Add To Your Wallet')}\n"
        f"{u('Example')}: <code>75</code>\n\n"
        f"{u('Minimum: Rs.1')}",
        keyboard)

async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles new value input for /editplan."""
    state = context.user_data.get("awaiting_edit")
    if not state:
        return
    pid   = state["pid"]
    field = state["field"]
    plan  = get_plan(pid)
    if not plan:
        await update.message.reply_text(b("❌ Plan not found."), parse_mode=ParseMode.HTML)
        context.user_data.pop("awaiting_edit", None)
        return

    raw = update.message.text_html if field == "description" else update.message.text.strip()

    if field == "price":
        try:
            raw = int(raw)
            if raw <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                f"❌ {b('Invalid price.')} {u('Send a number only, e.g.')} <code>299</code>",
                parse_mode=ParseMode.HTML,
            )
            return

    plans_col.update_one({"id": pid}, {"$set": {field: raw}})
    context.user_data.pop("awaiting_edit", None)

    label = {
        "channel": "Plan Name", "description": "Description", "price": "Price",
        "pay_description": "Payment Description", "channel_link": "Channel Link",
        "sample_link": "Sample Link",
    }.get(field, field)

    await update.message.reply_text(
        f"✅ {b(label)} {u('updated successfully for')} {b(plan['channel'])}",
        parse_mode=ParseMode.HTML,
    )


async def handle_custom_recharge_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text in REPLY_KB_TEXTS:
        return  # handled by reply_keyboard handler
    if context.user_data.get("awaiting_edit"):
        await handle_edit_input(update, context)
        return
    if not context.user_data.get("awaiting_recharge"):
        return
    text = update.message.text.strip()
    try:
        amt = int(text)
        if amt < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"❌ {b('Invalid Amount.')} {u('Please send a number, e.g.')} <code>75</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    context.user_data.pop("awaiting_recharge", None)

    keyboard = [
        [
            InlineKeyboardButton(u("Razorpay [ UPI / Cards ]"), callback_data=f"wrzp_{amt}"),
            InlineKeyboardButton(u("Pay with QR"),               callback_data=f"wqr_{amt}"),
        ],
        [
            InlineKeyboardButton(u("Pay with Crypto"), callback_data=f"wcrypto_{amt}"),
            InlineKeyboardButton(u("Coming Soon"),     callback_data="dummy_placeholder"),
        ],
        [InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data="menu_wallet")],
    ]
    await update.message.reply_text(
        f"💳 {b('Wallet Recharge')}\n\n"
        f"{b('Amount')}: Rs.{amt}\n\n"
        f"{b('Choose Your Payment Method')} 👇\n"
        f"{b('Once Payment Is Done Your Wallet Will Be Credited Automatically')}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def wallet_amount_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amt = int(query.data[len("wamt_"):])

    keyboard = [
        [
            InlineKeyboardButton(u("Razorpay [ UPI / Cards ]"), callback_data=f"wrzp_{amt}"),
            InlineKeyboardButton(u("Pay with QR"),               callback_data=f"wqr_{amt}"),
        ],
        [
            InlineKeyboardButton(u("Pay with Crypto"), callback_data=f"wcrypto_{amt}"),
            InlineKeyboardButton(u("Coming Soon"),     callback_data="dummy_placeholder"),
        ],
        [InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data="menu_wallet")],
    ]
    msg = (
        f"💳 {b('Wallet Recharge')}\n\n"
        f"{b('Amount')}: Rs.{amt}\n\n"
        f"{b('Choose Your Payment Method')} 👇\n"
        f"{b('Once Payment Is Done Your Wallet Will Be Credited Automatically')}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Wallet recharge: Razorpay ──────────────────────────────────────────────────
async def wallet_pay_razorpay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amt = int(query.data[len("wrzp_"):])

    try:
        pl = razorpay_client.payment_link.create({
            "amount":          amt * 100,
            "currency":        "INR",
            "accept_partial":  False,
            "description":     f"Wallet Recharge: Rs.{amt}",
            "notify":          {"sms": False, "email": False},
            "reminder_enable": False,
            "notes":           {"type": "wallet_recharge", "user_id": str(query.from_user.id), "amount": amt},
        })
        short_url = pl.get("short_url", "")
        link_id   = pl.get("id", "")
        pending_recharges[query.from_user.id] = {
            "amount": amt, "type": "link", "ref_id": link_id,
            "timestamp": time.time(), "short_url": short_url,
        }
        keyboard = [
            [InlineKeyboardButton(u("▶️ Open Payment Page"), url=short_url)],
            [InlineKeyboardButton(u("✅ I Have Paid"),       callback_data=f"wdone_link_{link_id}_{amt}")],
            [
                InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}"),
                InlineKeyboardButton(u("❌ Cancel"),  callback_data="menu_wallet"),
            ],
        ]
        msg = (
            f"💳 {b('Razorpay Payment')}\n\n"
            f"{b('Recharge Amount')}: Rs.{amt}\n\n"
            f"{b('Click The Button Below To Open The Payment Page')}\n"
            f"{b('Once Paid, Click I Have Paid Button')}"
        )
        await safe_edit(query, context, msg, keyboard)
    except Exception as e:
        logger.error(f"Wallet Razorpay link error: {e}")
        await safe_edit(query, context,
            f"❌ {b('Error creating payment. Please try again or contact support.')}\n@{SUPPORT_USERNAME}",
            [
                [InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
                [InlineKeyboardButton(u("🔙 Back"), callback_data=f"wamt_{amt}")],
            ])

# ── Wallet recharge: QR ────────────────────────────────────────────────────────
async def wallet_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amt = int(query.data[len("wqr_"):])

    _frames = [
        f"⏳ {b('Generating QR')}",
        f"⏳ {b('Generating QR')} ·",
        f"⏳ {b('Generating QR')} · ·",
        f"⏳ {b('Generating QR')} · · ·",
    ]
    await safe_edit(query, context, _frames[0], [])
    _msg = query.message

    async def _animate():
        for _i in range(1, 9999):
            await asyncio.sleep(0.7)
            try:
                await _msg.edit_text(_frames[_i % len(_frames)], parse_mode=ParseMode.HTML)
            except Exception:
                pass

    _anim = asyncio.create_task(_animate())
    buf, qr_id, gen_ok = None, "", False
    try:
        from PIL import Image as PilImage
        qr_resp = razorpay_client.qrcode.create({
            "type":           "upi_qr",
            "name":           "Wallet Recharge",
            "usage":          "single_use",
            "fixed_amount":   True,
            "payment_amount": amt * 100,
            "description":    f"Wallet Recharge: Rs.{amt}",
            "close_by":       int(time.time()) + 900,
        })
        qr_id     = qr_resp.get("id", "")
        image_url = qr_resp.get("image_url", "")
        with urllib.request.urlopen(image_url) as resp:
            img_bytes = resp.read()
        full_img = PilImage.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = full_img.size
        crop = full_img.crop((int(w*0.08), int(h*0.30), int(w*0.92), int(h*0.67)))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        buf.seek(0)
        gen_ok = True
    except Exception as e:
        logger.error(f"Wallet QR generation failed: {e}")
    finally:
        _anim.cancel()
        try:
            await _anim
        except asyncio.CancelledError:
            pass

    if gen_ok and buf:
        pending_recharges[query.from_user.id] = {
            "amount": amt, "type": "qr", "ref_id": qr_id, "timestamp": time.time(),
        }
        keyboard = [
            [InlineKeyboardButton(u("✅ I've Completed Payment"), callback_data=f"wdone_qr_{qr_id}_{amt}")],
            [
                InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}"),
                InlineKeyboardButton(u("❌ Cancel"),  callback_data="menu_wallet"),
            ],
        ]
        caption = (
            f"📱 {b('UPI Wallet Recharge')}\n\n"
            f"{b('Amount')}: Rs.{amt}\n\n"
            f"{b('Scan The QR Code Above Using Any UPI App')}\n"
            f"{b('Once Paid, Tap I ve Completed Payment')} ✅ {b('Below')}\n\n"
            f"{b('If You Are Not Able To Pay In This QR Code Please Try With Paytm, PhonePay Or Any Other Upi App')}\n\n"
            f"⏱️ {b('This QR Will Expire In 15 Minutes')}"
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
    else:
        await wallet_amount_selected(update, context)

# ── Wallet recharge: Crypto ────────────────────────────────────────────────────
def get_usdt_inr_rate():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=inr"
    with urllib.request.urlopen(url, timeout=6) as resp:
        data = json.loads(resp.read().decode())
    return float(data["tether"]["inr"])

async def wallet_pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amt = int(query.data[len("wcrypto_"):])

    await safe_edit(query, context, f"⏳ {b('Fetching Live Rate...')}", [])
    try:
        rate        = get_usdt_inr_rate()
        usdt_amount = amt / rate
        amount_line = f"{b('Amount')}: {usdt_amount:.2f} USDT  (Rs.{amt} @ Rs.{rate:.2f}/USDT)"
    except Exception as e:
        logger.error(f"USDT rate fetch failed: {e}")
        amount_line = f"{b('Amount')}: Rs.{amt} {b('(Live Rate Unavailable, Contact Admin For USDT Amount)')}"

    keyboard = [
        [InlineKeyboardButton(u("💬 Contact Admin"), url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back"),           callback_data=f"wamt_{amt}")],
    ]
    msg = (
        f"🌟 {b('Wallet Recharge Via Crypto (USDT)')}\n\n"
        f"{amount_line}\n\n"
        f"{b('Network')}: {b(CRYPTO_NETWORK)}\n"
        f"💼 {b('Wallet Address')}:\n\n<code>{CRYPTO_ADDRESS}</code>\n\n"
        f"{b('Tap The Address Above To Copy It')}\n\n"
        f"<blockquote>{b('Please Double Check The Network And Wallet Address Before Sending. Sending To A Wrong Network Or Address May Result In Permanent Loss Of Funds')}\n\n"
        f"{b('After Payment, Send The Screenshot Of Your Transaction To Admin')}</blockquote>"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Wallet recharge verification ───────────────────────────────────────────────
async def wallet_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rest  = query.data[len("wdone_"):]
    parts = rest.split("_", 2)
    ptype = parts[0]
    tail  = parts[1] if len(parts) > 1 else ""
    tail_parts     = tail.rsplit("_", 1)
    ref_id_from_cb = tail_parts[0] if len(tail_parts) > 1 else tail
    amt_from_cb    = int(tail_parts[1]) if len(tail_parts) > 1 and tail_parts[1].isdigit() else 0

    pending     = pending_recharges.get(query.from_user.id)
    stored_ref  = pending.get("ref_id", "") if pending else ref_id_from_cb
    stored_type = pending.get("type", ptype) if pending else ptype
    stored_amt  = pending.get("amount", amt_from_cb) if pending else amt_from_cb

    await safe_edit(query, context, f"⏳ {b('Verifying Payment... (1/5)')}", [])

    verified = False
    MAX_ATTEMPTS = 5
    for attempt in range(MAX_ATTEMPTS):
        try:
            if stored_type == "qr":
                payments = razorpay_client.qrcode.fetch_all_payments(stored_ref)
                for item in (payments.get("items") or []):
                    if item.get("status") == "captured":
                        verified = True
                        break
            else:
                details = razorpay_client.payment_link.fetch(stored_ref)
                if details.get("status") == "paid":
                    verified = True
        except Exception as e:
            logger.warning(f"Wallet payment check attempt {attempt + 1}: {e}")

        if verified:
            break
        if attempt < MAX_ATTEMPTS - 1:
            try:
                await query.message.edit_text(
                    f"⏳ {b(f'Verifying Payment... ({attempt + 2}/{MAX_ATTEMPTS})')}\n"
                    f"{b('Please wait, checking with payment gateway...')}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            await asyncio.sleep(4)

    if verified:
        pending_recharges.pop(query.from_user.id, None)
        credit_wallet(query.from_user.id, stored_amt, field="wallet_balance")
        wb, rb = get_wallet(query.from_user.id)
        keyboard = [
            [InlineKeyboardButton(u("🌟 Browse Subscriptions"), callback_data="menu_plans")],
            [InlineKeyboardButton(u("💰 Wallet"),               callback_data="menu_wallet")],
            [InlineKeyboardButton(u("🔙 Main Menu"),            callback_data="back_main")],
        ]
        msg = (
            f"✅ {b('Wallet Recharged Successfully')}\n\n"
            f"🌟 {b('Amount Added')}: Rs.{stored_amt}\n\n"
            f"{b('Your Wallet')}:\n"
            f"  {b('Recharge Balance')}: Rs.{wb}\n"
            f"  {b('Referral Balance')}: Rs.{rb}\n"
            f"  {b('Total Balance')}: Rs.{wb + rb}\n\n"
            f"{b('You Can Now Buy Subscriptions')} 👇"
        )
        await safe_edit(query, context, msg, keyboard)
    else:
        if stored_type == "qr":
            retry_row = [
                InlineKeyboardButton(u("🔄 Try Again"),     callback_data=query.data),
                InlineKeyboardButton(u("🔄 Regenerate QR"), callback_data=f"wqr_{stored_amt}"),
            ]
        else:
            pay_url = pending.get("short_url", "") if pending else ""
            retry_row = [InlineKeyboardButton(u("🔄 Try Again"), callback_data=query.data)]
            if pay_url:
                retry_row.append(InlineKeyboardButton(u("▶️ Payment Page"), url=pay_url))

        keyboard = [
            retry_row,
            [InlineKeyboardButton(u("💬 Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(u("🔙 Back"),    callback_data="menu_wallet")],
        ]
        msg = (
            f"❌ {b('Payment Not Verified Yet')}\n\n"
            f"{b('We Could Not Confirm Your Payment At This Time')}\n"
            f"{b('This Could Be Due To A Delay In The Payment System')}\n\n"
            f"{b('Please Wait A Moment And Try Again Or Contact Support')} @{SUPPORT_USERNAME}"
        )
        await safe_edit(query, context, msg, keyboard)

# ── Menu: Refer and Earn ───────────────────────────────────────────────────────
async def menu_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user     = query.from_user
    _, rb    = get_wallet(user.id)
    bot_name = context.bot.username
    ref_link = f"https://t.me/{bot_name}?start=ref_{user.id}"

    share_text = urllib.parse.quote(
        "Join this premium subscription bot and get exclusive content!\n\nUse my link to join"
    )
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"

    keyboard = [
        [InlineKeyboardButton(u("🔗 Share Referral Link"), url=share_url)],
        [InlineKeyboardButton(u("🔙 Main Menu"), callback_data="back_main")],
    ]
    msg = (
        f"🌟 {b('Refer and Earn')}\n\n"
        f"{b('Share Your Referral Link And Earn Rs.1 For Every New Member Who Joins')}\n\n"
        f"{b('Total Referral Earned')}: Rs.{rb}\n\n"
        f"💡 {b('How It Works')}:\n"
        f"  1. {b('Tap Share Referral Link below')}\n"
        f"  2. {b('Forward to your friends or groups')}\n"
        f"  3. {b('Rs.1 is instantly credited when they join')}\n"
        f"  4. {b('Use referral balance to buy subscriptions')}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Support / Developer ────────────────────────────────────────────────────────
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("🎧 Contact Admin"),  url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Main Menu"), callback_data="back_main")],
    ]
    msg = (
        f"🎧 {b('Support')}\n\n"
        f"{b('Need help? Our support team is here for you.')}\n\n"
        f"{b('Tap the button below to contact admin directly.')}"
    )
    await safe_edit(query, context, msg, keyboard)

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(u("💬 Contact Developer"), url=f"https://t.me/{DEV_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Main Menu"),          callback_data="back_main")],
    ]
    msg = (
        f"🌟 {b('Bot Developer / Creator')}\n\n"
        f"{b('This Bot Was Developed By')}: @{DEV_USERNAME}\n\n"
        f"{b('For Bot Related Queries Or Custom Bot Development Contact The Developer')}"
    )
    await safe_edit(query, context, msg, keyboard)

async def dummy_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(u("Coming soon!"), show_alert=True)

# ── /newplan ConversationHandler ───────────────────────────────────────────────
NP_NAME, NP_DESC, NP_PRICE, NP_PAYDESC, NP_LINK, NP_SAMPLE = range(6)

async def np_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin Only Command."), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        f"{b('New Plan — Step 1/6')}\n\n"
        f"{b('Send The Plan Name')} — {u('this will appear as the button text.')}\n\n"
        f"{u('Send /cancel to stop.')}",
        parse_mode=ParseMode.HTML,
    )
    return NP_NAME

async def np_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ {b('Name Saved')}: <b>{context.user_data['np_name']}</b>\n\n"
        f"{b('Step 2/6')} — {b('Send The Description.')}\n"
        f"{u('Any formatting (bold, spoiler, italic) will be preserved exactly as sent.')}",
        parse_mode=ParseMode.HTML,
    )
    return NP_DESC

async def np_got_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_desc"] = update.message.text_html
    await update.message.reply_text(
        f"✅ {b('Description Saved.')}\n\n"
        f"{b('Step 3/6')} — {b('Send The Price')} {u('(number only, e.g.')} <code>299</code>{u(')')}",
        parse_mode=ParseMode.HTML,
    )
    return NP_PRICE

async def np_got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"❌ {b('Invalid Price.')} {u('Send a number only, e.g.')} <code>299</code>",
            parse_mode=ParseMode.HTML,
        )
        return NP_PRICE
    context.user_data["np_price"] = price
    await update.message.reply_text(
        f"✅ {b('Price')}: Rs.{price}\n\n"
        f"{b('Step 4/6')} — {b('Send The Payment Description.')}\n"
        f"{u('This appears in Razorpay during payment, e.g.')}\n"
        f"<code>Subscription: HAWT PACK</code>",
        parse_mode=ParseMode.HTML,
    )
    return NP_PAYDESC

async def np_got_paydesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_paydesc"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ {b('Payment Description Saved.')}\n\n"
        f"{b('Step 5/6')} — {b('Send The Premium Channel Link.')}\n"
        f"{u('This is the invite link users get after successful payment, e.g.')}\n"
        f"<code>https://t.me/+xxxxxxxxxx</code>",
        parse_mode=ParseMode.HTML,
    )
    return NP_LINK

async def np_got_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_link"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ {b('Channel Link Saved.')}\n\n"
        f"{b('Step 6/6')} — {b('Send The Sample Content Link.')}\n"
        f"{u('Users will be taken to this link when they click View Sample Content, e.g.')}\n"
        f"<code>https://t.me/+xxxxxxxxxx</code>",
        parse_mode=ParseMode.HTML,
    )
    return NP_SAMPLE

async def np_got_sample(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sample_link  = update.message.text.strip()
    name         = context.user_data["np_name"]
    desc         = context.user_data["np_desc"]
    price        = context.user_data["np_price"]
    pay_desc     = context.user_data["np_paydesc"]
    channel_link = context.user_data["np_link"]
    pid          = uuid.uuid4().hex[:8]
    plans_col.insert_one({
        "id":              pid,
        "channel":         name,
        "description":     desc,
        "price":           price,
        "pay_description": pay_desc,
        "channel_link":    channel_link,
        "sample_link":     sample_link,
        "created_at":      datetime.now(timezone.utc),
    })
    await update.message.reply_text(
        f"✅ {b('Plan Added Successfully')}\n\n"
        f"{b('ID')}: <code>{pid}</code>\n"
        f"{b('Name')}: {name}\n"
        f"{b('Price')}: Rs.{price}\n"
        f"{b('Payment Description')}: {pay_desc}\n"
        f"{b('Channel Link')}: {channel_link}\n"
        f"{b('Sample Link')}: {sample_link}",
        parse_mode=ParseMode.HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END

async def np_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(b("❌ New Plan Cancelled."), parse_mode=ParseMode.HTML)
    return ConversationHandler.END

# ── /removeplan (admin) ────────────────────────────────────────────────────────
async def cmd_removeplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin Only Command."), parse_mode=ParseMode.HTML)
        return
    plans = get_all_plans()
    if not plans:
        await update.message.reply_text(b("❌ No Plans Found."), parse_mode=ParseMode.HTML)
        return
    keyboard = [
        [InlineKeyboardButton(f"❌ {p['channel']} — Rs.{p['price']}", callback_data=f"rmp_{p['id']}")]
        for p in plans
    ]
    keyboard.append([InlineKeyboardButton(u("❌ Cancel"), callback_data="rmp_cancel")])
    await update.message.reply_text(
        f"❌ {b('Remove Plan')}\n\n{b('Select The Plan You Want To Remove')} 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def rmp_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user):
        return
    pid  = query.data[len("rmp_"):]
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(b("❌ Plan Not Found."), parse_mode=ParseMode.HTML)
        return
    keyboard = [[
        InlineKeyboardButton(u("✅ Yes, Remove It"), callback_data=f"rmp_confirm_{pid}"),
        InlineKeyboardButton(u("❌ No, Cancel"),      callback_data="rmp_cancel"),
    ]]
    await query.edit_message_text(
        f"{b('Confirm Removal')}\n\n"
        f"{b('Are You Sure You Want To Remove')} <b>{plan['channel']}</b> (Rs.{plan['price']})?\n\n"
        f"{u('This action cannot be undone.')}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def rmp_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user):
        return
    pid  = query.data[len("rmp_confirm_"):]
    plan = get_plan(pid)
    if plan:
        plans_col.delete_one({"id": pid})
        await query.edit_message_text(
            f"✅ {b(plan['channel'])} {u('has been removed successfully.')}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await query.edit_message_text(b("❌ Plan Not Found."), parse_mode=ParseMode.HTML)

async def rmp_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(b("❌ Remove Cancelled."), parse_mode=ParseMode.HTML)

# ── How to Buy ─────────────────────────────────────────────────────────────────
async def how_to_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tutorial_link = get_tutorial_link()
    if tutorial_link:
        keyboard = [
            [InlineKeyboardButton(u("📖 Watch Tutorial"), url=tutorial_link)],
            [InlineKeyboardButton(u("🛍️ Browse Subscriptions"), callback_data="menu_plans")],
        ]
        msg = (
            f"❓ {b('How To Buy')}\n\n"
            f"{b('Follow these simple steps to subscribe:')}\n\n"
            f"1️⃣ {b('Recharge your wallet')} — {b('add balance using UPI, QR or Crypto')}\n"
            f"2️⃣ {b('Browse subscriptions')} — {b('pick the plan you want')}\n"
            f"3️⃣ {b('Pay from wallet')} — {b('one tap and you get the channel link instantly')}\n\n"
            f"📖 {b('Watch the full tutorial below for a step-by-step guide.')}"
        )
    else:
        keyboard = [
            [InlineKeyboardButton(u("🛍️ Browse Subscriptions"), callback_data="menu_plans")],
            [InlineKeyboardButton(u("🎧 Contact Support"), url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]
        msg = (
            f"❓ {b('How To Buy')}\n\n"
            f"{b('Follow these simple steps to subscribe:')}\n\n"
            f"1️⃣ {b('Recharge your wallet')} — {b('add balance using UPI, QR or Crypto')}\n"
            f"2️⃣ {b('Browse subscriptions')} — {b('pick the plan you want')}\n"
            f"3️⃣ {b('Pay from wallet')} — {b('one tap and you get the channel link instantly')}\n\n"
            f"💬 {b('Need help? Contact our support.')}"
        )
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, context, msg, keyboard)
    else:
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
        )

# ── Free Channel ───────────────────────────────────────────────────────────────
async def free_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = get_free_channel_link()
    if link:
        keyboard = [[InlineKeyboardButton(u("✅ Join Free Channel"), url=link)]]
        msg = (
            f"✅ {b('Free Channel')}\n\n"
            f"{b('Join our free channel to get regular updates and free content.')}\n\n"
            f"{b('Tap the button below to join.')}"
        )
    else:
        keyboard = []
        msg = f"✅ {b('Free channel not set yet.')} {u('Contact')} @{SUPPORT_USERNAME}"
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit(update.callback_query, context, msg, keyboard)
    else:
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
            parse_mode=ParseMode.HTML,
        )

# ── /set_freechannel <link> (admin) ────────────────────────────────────────────
async def cmd_set_freechannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{b('Usage')}: /set_freechannel {u('<link>')}",
            parse_mode=ParseMode.HTML,
        )
        return
    link = context.args[0].strip()
    set_setting("free_channel_link", link)
    await update.message.reply_text(
        f"✅ {b('Free channel link set to')}:\n{link}",
        parse_mode=ParseMode.HTML,
    )

# ── /remove_freechannel (admin) ────────────────────────────────────────────────
async def cmd_remove_freechannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    set_setting("free_channel_link", None)
    await update.message.reply_text(b("✅ Free channel link removed."), parse_mode=ParseMode.HTML)

# ── /set_tutorial <link> (admin) ───────────────────────────────────────────────
async def cmd_set_tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{b('Usage')}: /set_tutorial {u('<link>')}",
            parse_mode=ParseMode.HTML,
        )
        return
    link = context.args[0].strip()
    set_setting("tutorial_link", link)
    await update.message.reply_text(
        f"✅ {b('Tutorial link set to')}:\n{link}",
        parse_mode=ParseMode.HTML,
    )

# ── /remove_tutorial (admin) ───────────────────────────────────────────────────
async def cmd_remove_tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin only command."), parse_mode=ParseMode.HTML)
        return
    remove_setting("tutorial_link")
    await update.message.reply_text(b("✅ Tutorial link removed."), parse_mode=ParseMode.HTML)

# ── /editplan (admin) ─────────────────────────────────────────────────────────
_EP_FIELDS = {
    "channel":         "Plan Name",
    "description":     "Description",
    "price":           "Price (number)",
    "pay_description": "Payment Description",
    "channel_link":    "Channel Link",
    "sample_link":     "Sample Link",
}

async def cmd_editplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin Only Command."), parse_mode=ParseMode.HTML)
        return
    plans = get_all_plans()
    if not plans:
        await update.message.reply_text(b("❌ No Plans Found."), parse_mode=ParseMode.HTML)
        return
    keyboard = [
        [InlineKeyboardButton(f"✏️ {p['channel']} — Rs.{p['price']}", callback_data=f"ep_p_{p['id']}")]
        for p in plans
    ]
    keyboard.append([InlineKeyboardButton(u("❌ Cancel"), callback_data="ep_cancel")])
    await update.message.reply_text(
        f"✏️ {b('Edit Plan')}\n\n{b('Select The Plan You Want To Edit')} 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def ep_select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user):
        return
    pid  = query.data[len("ep_p_"):]
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(b("❌ Plan Not Found."), parse_mode=ParseMode.HTML)
        return
    keyboard = [
        [InlineKeyboardButton(u(label), callback_data=f"ep_f_{pid}_{field}")]
        for field, label in _EP_FIELDS.items()
    ]
    keyboard.append([InlineKeyboardButton(u("❌ Cancel"), callback_data="ep_cancel")])
    await query.edit_message_text(
        f"✏️ {b('Edit')} {b(plan['channel'])}\n\n{b('Which field do you want to change?')} 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def ep_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user):
        return
    rest  = query.data[len("ep_f_"):]
    pid, field = rest.rsplit("_", 1) if "_" in rest else (rest, "")
    # field names with underscores need special handling
    for f in _EP_FIELDS:
        if rest == f"{pid}_{f}" or rest.endswith(f"_{f}"):
            field = f
            pid   = rest[: len(rest) - len(f) - 1]
            break
    plan = get_plan(pid)
    if not plan:
        await query.edit_message_text(b("❌ Plan Not Found."), parse_mode=ParseMode.HTML)
        return
    label = _EP_FIELDS.get(field, field)
    context.user_data["awaiting_edit"] = {"pid": pid, "field": field}
    current = plan.get(field, "")
    if field == "description":
        current_display = u("(formatted text)")
    else:
        current_display = str(current)
    await query.edit_message_text(
        f"✏️ {b('Edit')} {b(label)}\n\n"
        f"{b('Current value')}: {current_display}\n\n"
        f"{b('Send the new value now:')}",
        parse_mode=ParseMode.HTML,
    )

async def ep_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("awaiting_edit", None)
    await query.edit_message_text(b("❌ Edit cancelled."), parse_mode=ParseMode.HTML)

# ── /help ─────────────────────────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_adm = is_admin(update.effective_user)
    msg = (
        f"📖 {b('Bot Commands')}\n\n"
        f"{'─' * 22}\n"
        f"👤 {b('User Commands')}\n"
        f"{'─' * 22}\n"
        f"/start — {u('Open the main menu')}\n"
        f"/help  — {u('Show this command list')}\n"
    )
    if is_adm:
        msg += (
            f"\n{'─' * 22}\n"
            f"🔧 {b('Admin Commands')}\n"
            f"{'─' * 22}\n"
            f"/stats            — {u('View total users, revenue & sales breakdown')}\n"
            f"/addbalance       — {u('Add wallet balance to a user')} <code>/addbalance user_id amount</code>\n"
            f"/check            — {u('Check payment records for a user')} <code>/check user_id amount</code>\n"
            f"/broadcast        — {u('Broadcast a message to all users (reply to a message)')}\n"
            f"/newplan          — {u('Add a new subscription plan (step-by-step)')}\n"
            f"/editplan         — {u('Edit name, price, description or links of any plan')}\n"
            f"/removeplan       — {u('Delete a subscription plan')}\n"
            f"/set_freechannel  — {u('Set the free channel link')} <code>/set_freechannel link</code>\n"
            f"/remove_freechannel — {u('Remove the free channel link')}\n"
            f"/set_tutorial     — {u('Set the How to Buy tutorial link')} <code>/set_tutorial link</code>\n"
            f"/remove_tutorial  — {u('Remove the tutorial link')}\n"
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ── Reply-keyboard button handler ──────────────────────────────────────────────
async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    save_user(update.effective_user)

    if text == BTN_FREE:
        await free_channel(update, context)

    elif text == BTN_REFER:
        # Simulate a fake callback_query-less refer call via message
        user     = update.effective_user
        _, rb    = get_wallet(user.id)
        bot_name = context.bot.username
        ref_link = f"https://t.me/{bot_name}?start=ref_{user.id}"
        share_text = urllib.parse.quote(
            "Join this premium subscription bot and get exclusive content!\n\nUse my link to join"
        )
        share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"
        keyboard = [
            [InlineKeyboardButton(u("🔗 Share Referral Link"), url=share_url)],
        ]
        msg = (
            f"🌟 {b('Refer and Earn')}\n\n"
            f"{b('Share Your Referral Link And Earn Rs.1 For Every New Member Who Joins')}\n\n"
            f"{b('Total Referral Earned')}: Rs.{rb}\n\n"
            f"💡 {b('How It Works')}:\n"
            f"  1. {b('Tap Share Referral Link below')}\n"
            f"  2. {b('Forward to your friends or groups')}\n"
            f"  3. {b('Rs.1 is instantly credited when they join')}\n"
            f"  4. {b('Use referral balance to buy subscriptions')}"
        )
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
        )

# ── Callback router ────────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    if   data == "menu_plans":             await menu_plans(update, context)
    elif data == "menu_about":             await menu_about(update, context)
    elif data == "menu_wallet":            await menu_wallet(update, context)
    elif data == "menu_refer":             await menu_refer(update, context)
    elif data == "menu_support":           await support(update, context)
    elif data == "menu_howtobuy":          await how_to_buy(update, context)
    elif data == "menu_dev":              await developer(update, context)
    elif data == "back_main":             await start(update, context)
    elif data == "bc_confirm":            await bc_confirm(update, context)
    elif data == "bc_cancel":             await bc_cancel(update, context)
    elif data == "ep_cancel":             await ep_cancel(update, context)
    elif data.startswith("ep_f_"):        await ep_select_field(update, context)
    elif data.startswith("ep_p_"):        await ep_select_plan(update, context)
    elif data == "rmp_cancel":            await rmp_cancel_cb(update, context)
    elif data.startswith("rmp_confirm_"): await rmp_confirm(update, context)
    elif data.startswith("rmp_"):         await rmp_select(update, context)
    elif data.startswith("showplan_"):    await show_plan(update, context)
    elif data.startswith("sample_"):      await sample_content(update, context)
    elif data.startswith("buy_"):         await buy_plan(update, context)
    elif data.startswith("wpay_"):        await wallet_pay_plan(update, context)
    elif data == "wamt_custom":           await wallet_custom_amount(update, context)
    elif data.startswith("wamt_"):        await wallet_amount_selected(update, context)
    elif data.startswith("wrzp_"):        await wallet_pay_razorpay(update, context)
    elif data.startswith("wqr_"):         await wallet_pay_qr(update, context)
    elif data.startswith("wcrypto_"):     await wallet_pay_crypto(update, context)
    elif data.startswith("wdone_"):       await wallet_done(update, context)
    elif data == "dummy_placeholder":     await dummy_placeholder(update, context)
