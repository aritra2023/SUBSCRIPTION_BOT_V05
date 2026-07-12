import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import (
    STORAGE_CHANNEL_ID, ADMIN_IDS,
    get_button, set_button, remove_button,
    get_running_batch, add_to_running_batch, clear_running_batch,
    save_batch, get_batch,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(user) -> bool:
    return bool(user and user.id in ADMIN_IDS)


def _delivery_keyboard(target_id: str | None = None) -> InlineKeyboardMarkup | None:
    """
    Returns keyboard with the button for target_id (or global fallback).
    Returns None if no button is configured.
    """
    btn = get_button(target_id)
    if not btn:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(btn["text"], url=btn["url"])]])


def _batch_status_keyboard(admin_id: int) -> InlineKeyboardMarkup:
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
                reply_markup=_delivery_keyboard(str(msg_id)),
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
        for mid in msg_ids:
            try:
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=STORAGE_CHANNEL_ID,
                    message_id=mid,
                    reply_markup=_delivery_keyboard(batch_id),
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
            InlineKeyboardButton("📦 Save in Batch",     callback_data=f"sib_{msg_id}"),
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

    # ── 🔗 Get Sharable Link ──
    if data.startswith("gsl_"):
        msg_id     = data[4:]
        share_link = f"https://t.me/{context.bot.username}?start=file_{msg_id}"
        await query.answer()
        await query.message.reply_text(
            f"🔗 <b>Sharable Link</b>\n\n"
            f"<b>File ID:</b>\n<code>{msg_id}</code>\n\n"
            f"<b>Link:</b>\n<code>{share_link}</code>",
            parse_mode=ParseMode.HTML,
        )

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
            f"<b>Batch ID:</b>\n<code>{batch_id}</code>\n\n"
            f"<b>Batch Link:</b>\n<code>{batch_link}</code>",
            parse_mode=ParseMode.HTML,
        )

    # ── 🗑 Clear batch ──
    elif data.startswith("clearbatch_"):
        clear_running_batch(admin_id)
        await query.edit_message_text("🗑 <b>Batch cleared.</b>", parse_mode=ParseMode.HTML)

    else:
        await query.answer()


# ── /addbutton ────────────────────────────────────────────────────────────────
# Formats:
#   /addbutton https://link.com_Button Name          → global (all files)
#   /addbutton <fileid>_https://link.com_Button Name → only that file
#   /addbutton <batchid>_https://link.com_Button Name → only that batch

async def cmd_addbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return

    text = update.message.text or ""

    # Try targeted: /addbutton <id>_https://..._ButtonName
    targeted = re.match(
        r"/addbutton\s+(\w+)_(https?://\S+)_(.+)",
        text, re.DOTALL,
    )
    # Try global: /addbutton https://..._ButtonName
    global_  = re.match(
        r"/addbutton\s+(https?://\S+)_(.+)",
        text, re.DOTALL,
    )

    if targeted:
        target_id = targeted.group(1).strip()
        url       = targeted.group(2).strip()
        btn_text  = targeted.group(3).strip()
        set_button(url, btn_text, target_id)
        await update.message.reply_text(
            f"✅ <b>Button saved for ID</b> <code>{target_id}</code>\n\n"
            f"<b>Text:</b> {btn_text}\n"
            f"<b>URL:</b> {url}\n\n"
            f"This button will appear only when that file/batch is delivered.",
            parse_mode=ParseMode.HTML,
        )
    elif global_:
        url      = global_.group(1).strip()
        btn_text = global_.group(2).strip()
        set_button(url, btn_text)
        await update.message.reply_text(
            f"✅ <b>Global button saved</b>\n\n"
            f"<b>Text:</b> {btn_text}\n"
            f"<b>URL:</b> {url}\n\n"
            f"This button will appear on every file that has no specific button set.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            "❌ <b>Wrong format.</b>\n\n"
            "<b>Global (all files):</b>\n"
            "<code>/addbutton https://link.com_Button Name</code>\n\n"
            "<b>Specific file/batch:</b>\n"
            "<code>/addbutton fileID_https://link.com_Button Name</code>\n"
            "<code>/addbutton batchID_https://link.com_Button Name</code>",
            parse_mode=ParseMode.HTML,
        )


# ── /removebutton ─────────────────────────────────────────────────────────────

async def cmd_removebutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("🔒 This bot is private.")
        return

    text = update.message.text or ""
    parts = text.split()

    if len(parts) >= 2:
        target_id = parts[1].strip()
        remove_button(target_id)
        await update.message.reply_text(
            f"✅ Button removed for ID <code>{target_id}</code>.",
            parse_mode=ParseMode.HTML,
        )
    else:
        remove_button()
        await update.message.reply_text("✅ Global button removed.")


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
        "<b>Single link</b> — Tap <b>🔗 Get Sharable Link</b>\n"
        "<b>Batch link</b>  — Tap <b>📦 Save in Batch</b> on each file → <b>📤 Get Batch Link</b>\n\n"
        "─────────────────\n"
        "<b>/addbutton</b>\n\n"
        "Global (all files):\n"
        "<code>/addbutton https://link.com_Button Name</code>\n\n"
        "Specific file:\n"
        "<code>/addbutton 12345_https://link.com_Button Name</code>\n\n"
        "Specific batch:\n"
        "<code>/addbutton a1b2c3d4e5_https://link.com_Button Name</code>\n\n"
        "<b>/removebutton</b> — Remove global button\n"
        "<b>/removebutton &lt;id&gt;</b> — Remove button for specific file/batch\n",
        parse_mode=ParseMode.HTML,
    )
