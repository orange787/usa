"""Main entry point for the Ops-Dev Requirement Bridge System."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

from src.core.config import get_settings, get_app_config
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator
from src.agents.tg_listener import TGListenerAgent
from src.agents.requirement_analyst import RequirementAnalystAgent
from src.agents.github_manager import GitHubManagerAgent
from src.agents.lark_dispatcher import LarkDispatcherAgent
from src.agents.status_sync import StatusSyncAgent
from src.services.llm.factory import create_llm
from src.services.github_service import GitHubService
from src.services.lark_service import LarkService
from src.bots.telegram_bot import create_telegram_app, start_telegram_polling, stop_telegram


def setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    settings = get_settings()
    config = get_app_config()

    logger.info("Starting Ops-Dev Requirement Bridge System...")

    # ── Initialize core ───────────────────────────────────────────────────
    event_bus = EventBus()

    # ── Initialize services ───────────────────────────────────────────────
    llm = create_llm()
    github_service = GitHubService()
    lark_service = LarkService()

    # ── Initialize agents ─────────────────────────────────────────────────
    tg_listener = TGListenerAgent(event_bus)
    analyst = RequirementAnalystAgent(llm)
    github_manager = GitHubManagerAgent(github_service)
    lark_dispatcher = LarkDispatcherAgent(event_bus, lark_service)
    status_sync = StatusSyncAgent(event_bus, llm)

    # Wire up status_sync agent references
    status_sync.set_agents(tg_listener, lark_dispatcher, github_manager)

    # ── Initialize orchestrator ───────────────────────────────────────────
    orchestrator = Orchestrator(event_bus)
    orchestrator.register_agents(
        tg_listener, analyst, github_manager, lark_dispatcher, status_sync
    )
    await orchestrator.setup()

    # ── Start event bus ───────────────────────────────────────────────────
    await event_bus.start()

    # ── Setup GitHub labels ───────────────────────────────────────────────
    try:
        await github_manager.setup_labels()
        logger.info("GitHub labels initialized")
    except Exception:
        logger.warning("Could not setup GitHub labels (check token/repo config)")

    # ── Start bots ────────────────────────────────────────────────────────
    tg_app = None
    lark_runner = None

    # Start Telegram bot
    if settings.telegram_bot_token:
        tg_app = create_telegram_app(tg_listener)
        await start_telegram_polling(tg_app)
        logger.info("Telegram bot started")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping Telegram bot")

    # Start Lark webhook server (only needed for full App mode, not custom webhook)
    if settings.lark_app_id:
        from src.bots.lark_bot import start_lark_server
        lark_runner = await start_lark_server(
            lark_dispatcher,
            port=settings.webhook_port,
        )
        logger.info("Lark webhook server started")
    elif settings.lark_webhook_url:
        logger.info("Lark custom webhook configured (push-only mode, no server needed)")
    else:
        logger.warning("No Lark config found, Lark notifications disabled")

    # ── Setup scheduled tasks ─────────────────────────────────────────────
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    digest_hour = config.get("scheduling", {}).get("daily_digest_hour", 10)
    digest_minute = config.get("scheduling", {}).get("daily_digest_minute", 0)

    scheduler.add_job(
        status_sync.generate_daily_digest,
        "cron",
        hour=digest_hour,
        minute=digest_minute,
        id="daily_digest",
    )

    scheduler.add_job(
        status_sync.check_escalations,
        "interval",
        hours=4,
        id="escalation_check",
    )

    scheduler.start()
    logger.info("Scheduler started (digest at %02d:%02d, escalation every 4h)", digest_hour, digest_minute)

    # ── Wait for shutdown ─────────────────────────────────────────────────
    logger.info("System is running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()

    def signal_handler():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await stop_event.wait()

    # ── Cleanup ───────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)

    if tg_app:
        await stop_telegram(tg_app)
    if lark_runner:
        await lark_runner.cleanup()

    await event_bus.stop()
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
