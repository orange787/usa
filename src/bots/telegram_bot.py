"""Telegram Bot entry point - sets up handlers and starts polling."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.core.config import get_settings
from src.agents.tg_listener import TGListenerAgent

logger = logging.getLogger(__name__)


def create_telegram_app(tg_listener: TGListenerAgent) -> Application:
    """Create and configure the Telegram bot application."""
    settings = get_settings()
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Store the bot reference in the agent
    tg_listener.bot = app.bot

    # Command handlers
    app.add_handler(CommandHandler("submit", tg_listener.handle_submit))
    app.add_handler(CommandHandler("status", tg_listener.handle_status))
    app.add_handler(CommandHandler("list", tg_listener.handle_list))
    app.add_handler(CommandHandler("help", tg_listener.handle_help))
    app.add_handler(CommandHandler("start", tg_listener.handle_help))

    # Reply handler for approval responses
    app.add_handler(
        MessageHandler(
            filters.REPLY & filters.TEXT & ~filters.COMMAND,
            tg_listener.handle_approval_reply,
        )
    )

    # General message handler (must be last)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            tg_listener.handle_message,
        )
    )

    logger.info("Telegram bot configured")
    return app


async def start_telegram_polling(app: Application) -> None:
    """Start the Telegram bot in polling mode."""
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    logger.info("Telegram bot polling started")


async def stop_telegram(app: Application) -> None:
    """Stop the Telegram bot."""
    if app.updater and app.updater.running:
        await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Telegram bot stopped")
