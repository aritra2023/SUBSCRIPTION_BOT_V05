import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from config import BOT_TOKEN
from handlers import (
    start, cmd_stats, cmd_broadcast, cmd_check, cmd_removeplan,
    bc_confirm, bc_cancel,
    handle_callback, handle_custom_recharge_input,
    np_start, np_got_name, np_got_desc, np_got_price,
    np_got_paydesc, np_got_link, np_got_sample, np_cancel,
    NP_NAME, NP_DESC, NP_PRICE, NP_PAYDESC, NP_LINK, NP_SAMPLE,
)
import logging

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # keep console clean, only bot logs matter


def _start_health_server():
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info(f"Health check server listening on port {port}")
    server.serve_forever()


def main():
    threading.Thread(target=_start_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    newplan_conv = ConversationHandler(
        entry_points=[CommandHandler("newplan", np_start)],
        states={
            NP_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, np_got_name)],
            NP_DESC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, np_got_desc)],
            NP_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, np_got_price)],
            NP_PAYDESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, np_got_paydesc)],
            NP_LINK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, np_got_link)],
            NP_SAMPLE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, np_got_sample)],
        },
        fallbacks=[CommandHandler("cancel", np_cancel)],
    )

    app.add_handler(newplan_conv)
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_recharge_input))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("broadcast",  cmd_broadcast))
    app.add_handler(CommandHandler("check",      cmd_check))
    app.add_handler(CommandHandler("removeplan", cmd_removeplan))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
