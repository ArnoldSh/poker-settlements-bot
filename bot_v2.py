from __future__ import annotations

import os

from telegram.ext import ApplicationBuilder

from poker_bot.handlers import register_handlers
from poker_bot.i18n import tr

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_URL = os.environ.get("BOT_WEBHOOK_URL")
WEBHOOK_SECRET_TOKEN = os.environ.get("BOT_WEBHOOK_SECRET_TOKEN")

def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError(tr("missing_bot_token"))
    if not WEBHOOK_URL:
        raise RuntimeError(tr("missing_webhook_url"))

    application = ApplicationBuilder().token(token).build()
    register_handlers(application)

    application.run_webhook(
        listen=HOST,
        port=PORT,
        webhook_url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET_TOKEN,
        close_loop=False,
    )


if __name__ == "__main__":
    main()
