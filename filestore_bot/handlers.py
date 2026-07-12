import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import (
    STORAGE_CHANNEL_ID, ADMIN_IDS,
    get_custom_button, set_custom_button, remove_custom_button,
    get_running_batch, add_to_running_batch, clear_running_batch,
    save_batch, get_batch,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(user) -> bool:
    return bool(user and user.id in ADMIN_IDS)


def _custom_btn_row() -> list | None:
    """Returns a keyboard row with the custom button, or None."""
    btn = get_custom_button()
    return [InlineKeyboardButton(btn["text"], url=btn["url"])] if btn else None


def _delivery_keyboard() -> InlineKeyboardMarkup | None:
    """Keyboard shown on delivered files — only the custom button, nothing else."""
    row = _custom_btn_row()
    return InlineKeyboardMarkup([row]) if row else None


def _batch_status_keyboard(admin_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown after adding a file to the running batch."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Get Batch Link", callback_data=f"finishbatch_{admin_id}"),
            InlineKeyboardButton("🗑 Clear Batch",    callback_data=f"clearbatch_{admin_id}"),
        ],
    ])


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return

    args = context.args

    # ── Single file deep-link: /start file_<msg_id> ──
    if args and args[0].startswith("file_"):
        try:
            msg_id = int(args[0][5:])
        except ValueError:
            await update.message.reply_text("❌ Invalid link.")
            return
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=STORAGE_CHANNEL_ID,
                message_id=msg_id,
                reply_markup=_delivery_keyboard(),
            )
        except Exception as e:
            logger.error("copy_message failed for file_%s: %s", msg_id, e)
            await update.message.reply_text("❌ File not found or no longer available.")
        return

    # ── Batch deep-link: /start batch_<batch_id> ──
    if args and args[0].startswith("batch_"):
        batch_id = args[0][6:]
        msg_ids  = get_batch(batch_id)
        if not msg_ids:
            await update.message.reply_text("❌ Batch not found or expired.")
            return
        total = len(msg_ids)
        for i, mid in enumerate(msg_ids):
            is_last = i == total - 1
            try:
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=STORAGE_CHANNEL_ID,
                    message_id=mid,
                    reply_markup=_delivery_keyboard() if is_last else None,
                )
            except Exception as e:
                logger.error("copy_message failed for batch file %s: %s", mid, e)
        return

    # ── Normal /start ──
    await update.message.reply_text("ʜɪ ! ɪ ᴀᴍ ᴀʟɪᴠᴇ . . . .")


# ── File handler (admin only) ─────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return

    try:
        fwd = await update.message.forward(chat_id=STORAGE_CHANNEL_ID)
    except Exception as e:
        logger.error("forward to storage channel failed: %s", e)
        await update.message.reply_text(
            "❌ Failed to store file. Make sure the bot is an admin in the storage channel."
        )
        return

    msg_id = fwd.message_id

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Save in Batch",    callback_data=f"sib_{msg_id}"),
            InlineKeyboardButton("🔗 Get Sharable Link", callback_data=f"gsl_{msg_id}"),
        ],
    ])

    await update.message.reply_text(
        f"✅ <b>File Stored</b>  |  ID: <code>{msg_id}</code>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


# ── Callback router ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user):
        await query.answer("🔒 Private bot.", show_alert=True)
        return

    data     = query.data
    admin_id = query.from_user.id

    # ── 🔗 Get Sharable Link → single file link shown as popup ──
    if data.startswith("gsl_"):
        msg_id     = data[4:]
        share_link = f"https://t.me/{context.bot.username}?start=file_{msg_id}"
        await query.answer(share_link, show_alert=True)

    # ── 📦 Save in Batch ──
    elif data.startswith("sib_"):
        msg_id  = int(data[4:])
        current = add_to_running_batch(admin_id, msg_id)
        count   = len(current)
        await query.edit_message_text(
            f"📦 <b>Added to batch!</b>  (<b>{count}</b> file{'s' if count != 1 else ''} so far)\n\n"
            f"Keep sending files and tap <b>Save in Batch</b> on each,\n"
            f"then tap <b>Get Batch Link</b> when done.",
            reply_markup=_batch_status_keyboard(admin_id),
            parse_mode=ParseMode.HTML,
        )

    # ── 📤 Finish batch → generate batch link ──
    elif data.startswith("finishbatch_"):
        msg_ids = get_running_batch(admin_id)
        if not msg_ids:
            await query.answer("No files in batch yet!", show_alert=True)
            return
        batch_id   = save_batch(msg_ids)
        batch_link = f"https://t.me/{context.bot.username}?start=batch_{batch_id}"
        clear_running_batch(admin_id)
        await query.edit_message_text(
            f"✅ <b>Batch saved!</b>  ({len(msg_ids)} files)\n\n"
            f"<b>Batch Link:</b>\n<code>{batch_link}</code>",
            parse_mode=ParseMode.HTML,
        )

    # ── 🗑 Clear batch ──
    elif data.startswith("clearbatch_"):
        clear_running_batch(admin_id)
        await query.edit_message_text(
            "🗑 <b>Batch cleared.</b>",
            parse_mode=ParseMode.HTML,
        )

    else:
        await query.answer()


# ── /addbutton ────────────────────────────────────────────────────────────────

async def cmd_addbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return

    match = re.match(
        r"/addbutton\s+(https?://\S+)\s+\[(.+?)\]",
        update.message.text or "",
        re.DOTALL,
    )
    if not match:
        await update.message.reply_text(
            "❌ <b>Wrong format.</b>\n\n"
            "Use: <code>/addbutton https://yourlink.com [Button Name]</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    url, btn_text = match.group(1).strip(), match.group(2).strip()
    set_custom_button(url, btn_text)
    await update.message.reply_text(
        f"✅ <b>Button saved!</b>\n\n"
        f"<b>Text:</b> {btn_text}\n"
        f"<b>URL:</b> {url}\n\n"
        f"This button will appear below every delivered file.",
        parse_mode=ParseMode.HTML,
    )


# ── /removebutton ─────────────────────────────────────────────────────────────

async def cmd_removebutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return
    remove_custom_button()
    await update.message.reply_text("✅ Custom button removed.")


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return
    await update.message.reply_text(
        "📖 <b>File Store Bot</b>\n\n"
        "/start — Open bot\n"
        "/help  — This list\n\n"
        "🔧 <b>Admin</b>\n\n"
        "<b>Store file</b> — Send any file to the bot\n\n"
        "<b>Single link</b> — Tap <b>Get Sharable Link</b> → one file, one link\n\n"
        "<b>Batch link</b> — Tap <b>Save in Batch</b> on each file you want grouped,\n"
        "then tap <b>Get Batch Link</b> → one link, all files delivered together\n\n"
        "/addbutton <code>https://link.com [Button Name]</code>\n"
        "  → URL button shown on every delivery\n\n"
        "/removebutton — Remove the custom button\n",
        parse_mode=ParseMode.HTML,
    )
