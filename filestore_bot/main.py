import logging
import sys

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN
from handlers import (
    cmd_start, handle_file, handle_callback,
    cmd_addbutton, cmd_removebutton, cmd_help,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not BOT_TOKEN:
        logger.error(
            "TELEGRAM_DEMO_BOT_TOKEN is not set. "
            "Add it as a secret in Replit and restart."
        )
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(CommandHandler("addbutton",     cmd_addbutton))
    app.add_handler(CommandHandler("removebutton",  cmd_removebutton))

    # Any file type
    app.add_handler(MessageHandler(
        filters.Document.ALL
        | filters.VIDEO
        | filters.AUDIO
        | filters.PHOTO
        | filters.VOICE
        | filters.VIDEO_NOTE
        | filters.Sticker.ALL,
        handle_file,
    ))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("File Store Bot is starting…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
