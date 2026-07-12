import re
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import (
    STORAGE_CHANNEL_ID, ADMIN_IDS,
    get_custom_button, set_custom_button, remove_custom_button,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(user) -> bool:
    return bool(user and user.id in ADMIN_IDS)


def _file_keyboard(bot_username: str, msg_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown below a delivered file."""
    share_link = f"https://t.me/{bot_username}?start=file_{msg_id}"
    rows = [
        [
            InlineKeyboardButton("📦 Save in Batch",    callback_data=f"batch_{msg_id}"),
            InlineKeyboardButton("🔗 Get Sharable Link", callback_data=f"getlink_{msg_id}"),
        ],
    ]
    btn = get_custom_button()
    if btn:
        rows.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
    return InlineKeyboardMarkup(rows)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    # Deep-link: /start file_<msg_id>
    if args and args[0].startswith("file_"):
        try:
            msg_id = int(args[0][5:])
        except ValueError:
            await update.message.reply_text("❌ Invalid link.")
            return

        try:
            # Copy without forward tag
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=STORAGE_CHANNEL_ID,
                message_id=msg_id,
            )
            await update.message.reply_text(
                "Choose an option from below:",
                reply_markup=_file_keyboard(context.bot.username, msg_id),
            )
        except Exception as e:
            logger.error("copy_message failed: %s", e)
            await update.message.reply_text("❌ File not found or no longer available.")
        return

    # Normal start
    await update.message.reply_text(
        "👋 <b>File Store Bot</b>\n\n"
        "Send me any file and I'll store it and generate a shareable link for you.\n\n"
        "Use /help to see all commands.",
        parse_mode=ParseMode.HTML,
    )


# ── File handler (admin only) ─────────────────────────────────────────────────

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Only admins can store files.")
        return

    try:
        fwd = await update.message.forward(chat_id=STORAGE_CHANNEL_ID)
    except Exception as e:
        logger.error("forward to storage channel failed: %s", e)
        await update.message.reply_text(
            "❌ Failed to store file. Make sure the bot is an admin in the storage channel."
        )
        return

    msg_id     = fwd.message_id
    share_link = f"https://t.me/{context.bot.username}?start=file_{msg_id}"

    await update.message.reply_text(
        f"✅ <b>File Stored!</b>\n\n"
        f"<b>Message ID:</b> <code>{msg_id}</code>\n\n"
        f"<b>Shareable Link:</b>\n"
        f"<code>{share_link}</code>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔗 Get Sharable Link", url=share_link),
        ]]),
        parse_mode=ParseMode.HTML,
    )


# ── Callback router ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data

    if data.startswith("getlink_"):
        msg_id     = data[8:]
        share_link = f"https://t.me/{context.bot.username}?start=file_{msg_id}"
        await query.answer(share_link, show_alert=True)

    elif data.startswith("batch_"):
        await query.answer(
            "Batch feature coming soon! Share the link to let others access this file.",
            show_alert=True,
        )

    else:
        await query.answer()


# ── /addbutton ────────────────────────────────────────────────────────────────

async def cmd_addbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Admin only.")
        return

    # Format: /addbutton https://link.com [Button Name]
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
        f"This button will now appear below every file that's delivered.",
        parse_mode=ParseMode.HTML,
    )


# ── /removebutton ─────────────────────────────────────────────────────────────

async def cmd_removebutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Admin only.")
        return
    remove_custom_button()
    await update.message.reply_text("✅ Custom button removed from all future deliveries.")


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    adm = is_admin(update.effective_user)
    msg = (
        "📖 <b>File Store Bot — Commands</b>\n\n"
        "/start — Open bot\n"
        "/help  — Show this list\n"
    )
    if adm:
        msg += (
            "\n🔧 <b>Admin Commands</b>\n\n"
            "<b>Store a file</b> — Just send any file to the bot\n\n"
            "/addbutton <code>https://link.com [Button Name]</code>\n"
            "  → Adds a URL button to every delivered file\n\n"
            "/removebutton\n"
            "  → Removes the custom URL button\n"
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
