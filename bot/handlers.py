import asyncio
import io
import json
import time
import uuid
import urllib.request
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import (
    ADMIN_USERNAME, ADMIN_IDS, PREMIUM_CHANNEL_LINK,
    CRYPTO_NETWORK, CRYPTO_ADDRESS,
    razorpay_client, users_col, pays_col, plans_col,
    pending_payments, pending_broadcasts,
    get_all_plans, get_plan,
)
from utils import u, b, is_admin, safe_edit, save_user, record_payment

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    keyboard = [
        [InlineKeyboardButton(u("Available Subscription"),         callback_data="menu_plans")],
        [InlineKeyboardButton(u("Your Paid Subscriptions"),        callback_data="menu_mysubs")],
        [
            InlineKeyboardButton(u("Support"), callback_data="menu_support"),
            InlineKeyboardButton(u("Creator"), callback_data="menu_dev"),
        ],
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
        f"📤 {b('Broadcasting...')} 0/{len(all_users)}", parse_mode=ParseMode.HTML,
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
            import logging; logging.getLogger(__name__).warning(f"Broadcast failed for {usr['user_id']}: {e}")
            fail += 1
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"📤 {b('Broadcasting...')} {i+1}/{len(all_users)}", parse_mode=ParseMode.HTML,
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
    await query.edit_message_text(f"❌ {b('Broadcast cancelled.')}", parse_mode=ParseMode.HTML)

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
        import logging; logging.getLogger(__name__).warning(f"/check Razorpay error: {e}")

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
    keyboard = [[InlineKeyboardButton(u(p["channel"]), callback_data=f"showplan_{p['id']}")] for p in get_all_plans()]
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
    sample_link = plan.get("sample_link")
    keyboard = [
        [
            InlineKeyboardButton(u("👁 View Sample Content"), url=sample_link) if sample_link
            else InlineKeyboardButton(u("👁 View Sample Content"), callback_data=f"sample_{pid}"),
            InlineKeyboardButton(u("📸 Payment Proof"), url=PREMIUM_CHANNEL_LINK),
        ],
        [InlineKeyboardButton(f"₹{plan['price']} - " + u("Permanent"), callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data="menu_plans")],
    ]
    desc = plan.get("description", "")
    msg = (
        f"📺 {b(plan['channel'])}\n\n"
        f"{desc}\n\n"
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
        [
            InlineKeyboardButton(u("Razorpay [UPI/ CARDS]"), callback_data=f"rzp_{pid}"),
            InlineKeyboardButton(u("Pay with QR"),            callback_data=f"qr_{pid}"),
        ],
        [
            InlineKeyboardButton(u("Pay with Crypto"), callback_data=f"crypto_{pid}"),
            InlineKeyboardButton(u("Coming Soon"),     callback_data="dummy_placeholder"),
        ],
        [InlineKeyboardButton(u("Support"), url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back"), callback_data=f"showplan_{pid}")],
    ]
    msg = (
        f"{b('Choose your payment method')}:\n\n"
        f"{b('Channel')}: {b(plan['channel'])}\n"
        f"{b('Plan')}: {b('Permanent')}\n"
        f"{b('Amount')}: ₹{plan['price']}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── Payment handlers ───────────────────────────────────────────────────────────
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
            "amount":          plan["price"] * 100,
            "currency":        "INR",
            "accept_partial":  False,
            "description":     plan.get("pay_description", f"Subscription: {plan['channel']}"),
            "notify":          {"sms": False, "email": False},
            "reminder_enable": False,
            "notes":           {"plan_id": pid, "user_id": str(query.from_user.id)},
        })
        short_url = pl.get("short_url", "")
        link_id   = pl.get("id", "")
        pending_payments[query.from_user.id] = {
            "pid": pid, "type": "link", "ref_id": link_id,
            "amount": plan["price"], "timestamp": time.time(),
            "short_url": short_url,
        }
        keyboard = [
            [InlineKeyboardButton(u("💳 Open Payment Page"), url=short_url)],
            [InlineKeyboardButton(u("✅ I Have Paid"),        callback_data=f"paid_{pid}_link_{link_id}")],
            [InlineKeyboardButton(u("Support"),            url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton(u("❌ Cancel"),             callback_data=f"showplan_{pid}")],
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
        import logging; logging.getLogger(__name__).error(f"Razorpay link error: {e}")
        await safe_edit(query, context,
            f"❌ {b('Error creating payment. Please try again or contact support.')}\n@{ADMIN_USERNAME}",
            [
                [InlineKeyboardButton(u("Support"), url=f"https://t.me/{ADMIN_USERNAME}")],
                [InlineKeyboardButton(u("🔙 Back"), callback_data=f"buy_{pid}")],
            ])

async def pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("qr_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return

    # Animated loading while QR generates
    _frames = [
        f"⏳ {b('Generating QR')}",
        f"⏳ {b('Generating QR')} ·",
        f"⏳ {b('Generating QR')} · ·",
        f"⏳ {b('Generating QR')} · · ·",
    ]
    await safe_edit(query, context, _frames[0], [])
    _msg = query.message  # same chat/message id — safe to edit in loop

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
            "name":           "Premium Subscription",
            "usage":          "single_use",
            "fixed_amount":   True,
            "payment_amount": plan["price"] * 100,
            "description":    plan.get("pay_description", f"Subscription: {plan['channel']}"),
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
        import logging; logging.getLogger(__name__).error(f"QR generation failed: {e}")
    finally:
        _anim.cancel()
        try:
            await _anim
        except asyncio.CancelledError:
            pass

    if gen_ok and buf:
        pending_payments[query.from_user.id] = {
            "pid": pid, "type": "qr", "ref_id": qr_id,
            "amount": plan["price"], "timestamp": time.time(),
        }
        keyboard = [
            [InlineKeyboardButton(u("✅ I've Completed Payment"), callback_data=f"paid_{pid}_qr_{qr_id}")],
            [InlineKeyboardButton(u("Support"),                url=f"https://t.me/{ADMIN_USERNAME}")],
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
    else:
        await buy_plan(update, context)

def get_usdt_inr_rate():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=inr"
    with urllib.request.urlopen(url, timeout=6) as resp:
        data = json.loads(resp.read().decode())
    return float(data["tether"]["inr"])

async def pay_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid  = query.data[len("crypto_"):]
    plan = get_plan(pid)
    if not plan:
        await safe_edit(query, context, b("Plan not found."), [])
        return

    await safe_edit(query, context, f"⏳ {b('Fetching Live Rate...')}", [])

    try:
        rate        = get_usdt_inr_rate()
        usdt_amount = plan["price"] / rate
        amount_line = f"{b('Amount')}: {usdt_amount:.2f} USDT  (₹{plan['price']} @ ₹{rate:.2f}/USDT)"
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"USDT rate fetch failed: {e}")
        amount_line = f"{b('Amount')}: ₹{plan['price']} {b('(Live Rate Unavailable, Contact Admin For USDT Amount)')}"

    keyboard = [
        [InlineKeyboardButton(u("Contact Admin"), url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(u("🔙 Back"),        callback_data=f"buy_{pid}")],
    ]
    msg = (
        f"{b('Pay With Crypto (USDT)')}\n\n"
        f"{b('Channel')}: {b(plan['channel'])}\n"
        f"{b('Plan')}: {b('Permanent')}\n"
        f"{amount_line}\n\n"
        f"{b('Network')}: {b(CRYPTO_NETWORK)}\n"
        f"{b('Wallet Address')}:\n<code>{CRYPTO_ADDRESS}</code>\n"
        f"{b('Tap The Address Above To Copy It')}\n\n"
        f"⚠️ {b('Please Double Check The Network And Wallet Address Before Sending. Sending To A Wrong Network Or Address May Result In Permanent Loss Of Funds')}\n\n"
        f"{b('After Payment, Send The Screenshot Of Your Transaction To Admin')}"
    )
    await safe_edit(query, context, msg, keyboard)

async def dummy_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(u("Coming soon!"), show_alert=True)

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rest  = query.data[len("paid_"):]
    parts = rest.split("_", 2)
    pid   = parts[0]
    ptype = parts[1] if len(parts) > 1 else "link"
    plan  = get_plan(pid)

    try:
        pending = pending_payments.get(query.from_user.id)
        if not pending:
            raise ValueError("no_pending")

        stored_ref  = pending.get("ref_id", "")
        stored_type = pending.get("type", "link")
        stored_pid  = pending.get("pid", "")

        if stored_pid and stored_pid != pid:
            raise ValueError("plan_mismatch")
        if not stored_ref:
            raise ValueError("no_ref")

        await safe_edit(query, context, f"🔄 {b('Checking Payment...')}", [])

        verified = False

        if stored_type == "qr":
            # ── QR: check via Razorpay QR payments API ────────────────────────
            payments = razorpay_client.qrcode.fetch_all_payments(stored_ref)
            for item in (payments.get("items") or []):
                if item.get("status") == "captured":
                    verified = True
                    break
        else:
            # ── Link: check payment link status ───────────────────────────────
            details = razorpay_client.payment_link.fetch(stored_ref)
            if details.get("status") == "paid":
                verified = True

        if verified and plan:
            pending_payments.pop(query.from_user.id, None)
            newly_inserted = record_payment(query.from_user.id, plan, stored_ref, stored_type)
            if not newly_inserted:
                # Already recorded — still give them the link (idempotent grant)
                keyboard = [
                    [InlineKeyboardButton(u("🔓 Join Premium Channel"), url=plan.get("channel_link", PREMIUM_CHANNEL_LINK))],
                    [InlineKeyboardButton(u("Support"),               url=f"https://t.me/{ADMIN_USERNAME}")],
                    [InlineKeyboardButton(u("🏠 Back to Main Menu"),    callback_data="back_main")],
                ]
                await safe_edit(
                    query, context,
                    f"✅ {b('Payment Already Recorded')}\n\n"
                    f"{b('Your subscription is active. Click below to join.')} 👇",
                    keyboard,
                )
                return
            keyboard = [
                [InlineKeyboardButton(u("🔓 Join Premium Channel"), url=plan.get("channel_link", PREMIUM_CHANNEL_LINK))],
                [InlineKeyboardButton(u("Support"),               url=f"https://t.me/{ADMIN_USERNAME}")],
                [InlineKeyboardButton(u("🏠 Back to Main Menu"),    callback_data="back_main")],
            ]
            msg = (
                f"✅ {b('Payment Verified Successfully!')}\n\n"
                f"🎉 {b('Welcome To')} {b(plan['channel'])}!\n\n"
                f"{b('Click The Button Below To Join Your Premium Channel')} 👇\n\n"
                f"{b('If You Face Any Issue Contact')}: @{ADMIN_USERNAME}\n\n"
                f"{b('Thank you for your purchase!')}"
            )
            await safe_edit(query, context, msg, keyboard)
        else:
            raise ValueError("not_verified")
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"Payment check: {e}")
        pending_info = pending_payments.get(query.from_user.id)
        if ptype == "qr":
            retry_row = [
                InlineKeyboardButton(u("🔄 Try Again"),     callback_data=f"paid_{pid}_qr_"),
                InlineKeyboardButton(u("📱 Regenerate QR"), callback_data=f"qr_{pid}"),
            ]
        else:
            pay_url = pending_info.get("short_url", "") if pending_info else ""
            retry_row = [InlineKeyboardButton(u("🔄 Try Again"), callback_data=f"paid_{pid}_link_")]
            if pay_url:
                retry_row.append(InlineKeyboardButton(u("💳 Payment Page"), url=pay_url))
        keyboard = [
            retry_row,
            [InlineKeyboardButton(u("Support"), url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton(u("🔙 Back to Main Menu"), callback_data="back_main")],
        ]
        msg = (
            f"❌ {b('Payment Not Verified Yet')}\n\n"
            f"{b('We Couldn t Confirm Your Payment At This Time')}\n"
            f"{b('This Could Be Due To A Delay In The Payment System')}\n\n"
            f"{b('Please Wait A Moment And Try Again Or Contact Support')} @{ADMIN_USERNAME}"
        )
        await safe_edit(query, context, msg, keyboard)

# ── My Subscriptions / Support / Developer ────────────────────────────────────
async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    pays = list(pays_col.find({"user_id": uid}, {"_id": 0, "plan_name": 1, "amount": 1, "paid_at": 1}))
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
        [InlineKeyboardButton(u("🔙 Back to Main Menu"),  callback_data="back_main")],
    ]
    msg = (
        f"👨‍💻 {b('Bot Developer/Creator')}\n\n"
        f"{b('This Bot Was Developed By')}: @{ADMIN_USERNAME}\n\n"
        f"{b('For Bot Related Queries Or Custom Bot Development Contact The Developer')}"
    )
    await safe_edit(query, context, msg, keyboard)

# ── /newplan ConversationHandler ──────────────────────────────────────────────
NP_NAME, NP_DESC, NP_PRICE, NP_PAYDESC, NP_LINK, NP_SAMPLE = range(6)

async def np_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text(b("❌ Admin Only Command."), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        f"➕ {b('New Plan — Step 1/6')}\n\n"
        f"{b('Send The Plan Name')} — {u('this will appear as the button text.')}\n\n"
        f"{u('Send /cancel to stop.')}",
        parse_mode=ParseMode.HTML,
    )
    return NP_NAME

async def np_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ {b('Name Saved')}: <b>{context.user_data['np_name']}</b>\n\n"
        f"➕ {b('Step 2/6')} — {b('Send The Description.')}\n"
        f"{u('Any formatting (bold, spoiler, italic) will be preserved exactly as sent.')}",
        parse_mode=ParseMode.HTML,
    )
    return NP_DESC

async def np_got_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_desc"] = update.message.text_html
    await update.message.reply_text(
        f"✅ {b('Description Saved.')}\n\n"
        f"➕ {b('Step 3/6')} — {b('Send The Price')} {u('(number only, e.g.')} <code>299</code>{u(')')}",
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
        f"✅ {b('Price')}: ₹{price}\n\n"
        f"➕ {b('Step 4/6')} — {b('Send The Payment Description.')}\n"
        f"{u('This appears in Razorpay during payment, e.g.')}\n"
        f"<code>Subscription: HAWT PACK</code>",
        parse_mode=ParseMode.HTML,
    )
    return NP_PAYDESC

async def np_got_paydesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_paydesc"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ {b('Payment Description Saved.')}\n\n"
        f"➕ {b('Step 5/6')} — {b('Send The Premium Channel Link.')}\n"
        f"{u('This is the invite link users get after successful payment, e.g.')}\n"
        f"<code>https://t.me/+xxxxxxxxxx</code>",
        parse_mode=ParseMode.HTML,
    )
    return NP_LINK

async def np_got_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["np_link"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ {b('Channel Link Saved.')}\n\n"
        f"➕ {b('Step 6/6')} — {b('Send The Sample Content Link.')}\n"
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
        f"✅ {b('Plan Added Successfully!')} 🎉\n\n"
        f"🆔 {b('ID')}: <code>{pid}</code>\n"
        f"📌 {b('Name')}: {name}\n"
        f"💰 {b('Price')}: ₹{price}\n"
        f"📝 {b('Payment Description')}: {pay_desc}\n"
        f"🔗 {b('Channel Link')}: {channel_link}\n"
        f"👁 {b('Sample Link')}: {sample_link}",
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
        [InlineKeyboardButton(f"🗑 {p['channel']} — ₹{p['price']}", callback_data=f"rmp_{p['id']}")]
        for p in plans
    ]
    keyboard.append([InlineKeyboardButton(u("❌ Cancel"), callback_data="rmp_cancel")])
    await update.message.reply_text(
        f"🗑 {b('Remove Plan')}\n\n{b('Select The Plan You Want To Remove')} 👇",
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
        InlineKeyboardButton(u("❌ No, Cancel"),     callback_data="rmp_cancel"),
    ]]
    await query.edit_message_text(
        f"⚠️ {b('Confirm Removal')}\n\n"
        f"{b('Are You Sure You Want To Remove')} <b>{plan['channel']}</b> (₹{plan['price']})?\n\n"
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

# ── Callback router ────────────────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    uid  = update.callback_query.from_user.id

    if   data == "menu_plans":             await menu_plans(update, context)
    elif data == "menu_mysubs":            await my_subscriptions(update, context)
    elif data == "menu_support":           await support(update, context)
    elif data == "menu_dev":              await developer(update, context)
    elif data == "back_main":             await start(update, context)
    elif data == "bc_confirm":            await bc_confirm(update, context)
    elif data == "bc_cancel":             await bc_cancel(update, context)
    elif data == "rmp_cancel":            await rmp_cancel_cb(update, context)
    elif data.startswith("rmp_confirm_"): await rmp_confirm(update, context)
    elif data.startswith("rmp_"):         await rmp_select(update, context)
    elif data.startswith("showplan_"):    await show_plan(update, context)
    elif data.startswith("sample_"):      await sample_content(update, context)
    elif data.startswith("buy_"):         await buy_plan(update, context)
    elif data.startswith("rzp_"):         await pay_razorpay(update, context)
    elif data.startswith("qr_"):          await pay_qr(update, context)
    elif data.startswith("crypto_"):      await pay_crypto(update, context)
    elif data == "dummy_placeholder":     await dummy_placeholder(update, context)
    elif data.startswith("paid_"):        await i_have_paid(update, context)
