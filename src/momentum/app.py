"""Builds the Dispatcher, wires the scheduler, and runs polling or webhook."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from momentum.config import settings
from momentum.db.engine import close_db, init_db
from momentum.handlers import add_workout, admin, common, history, suggestions
from momentum.handlers import reports as reports_handlers
from momentum.scheduler import build_scheduler
from momentum.texts import admin as texts_admin
from momentum.texts import common as texts_common

log = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Outer middleware so the user row exists before any handler (or filter) runs.
    dp.update.outer_middleware(common.UserMiddleware())

    dp.include_router(common.router)
    # Before the FSM-scoped routers so /admin works mid-flow, like /cancel does.
    dp.include_router(admin.router)
    dp.include_router(admin.denied_router)
    dp.include_router(add_workout.router)
    dp.include_router(history.router)
    dp.include_router(reports_handlers.router)
    dp.include_router(suggestions.router)
    return dp


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command=name, description=desc)
        for name, desc in texts_common.COMMAND_DESCRIPTIONS
    ]
    await bot.set_my_commands(commands)

    # Discoverability only — authorization is the router filter, not the scope.
    admin_commands = [
        *commands,
        BotCommand(command="admin", description=texts_admin.ADMIN_COMMAND_DESCRIPTION),
    ]
    for admin_id in sorted(settings.ADMIN_USER_IDS):
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except TelegramAPIError:
            log.warning("Could not register admin commands for %s", admin_id, exc_info=True)


# --------------------------------------------------------------------------
# Run modes
# --------------------------------------------------------------------------


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    log.info("Starting in polling mode")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    secret = settings.WEBHOOK_SECRET.get_secret_value()

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret or None).register(
        app, path=settings.WEBHOOK_PATH
    )
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        settings.webhook_url,
        secret_token=secret or None,
        drop_pending_updates=True,
    )
    log.info("Webhook set to %s", settings.webhook_url)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.WEB_HOST, port=settings.WEB_PORT)
    await site.start()
    log.info("Listening on %s:%s%s", settings.WEB_HOST, settings.WEB_PORT, settings.WEBHOOK_PATH)

    try:
        await asyncio.Event().wait()  # run until cancelled / interrupted
    finally:
        await bot.delete_webhook()
        await runner.cleanup()


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------


async def main() -> None:
    setup_logging()
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    dp.startup.register(set_commands)

    scheduler = build_scheduler(bot)
    scheduler.start()

    try:
        if settings.BOT_MODE == "webhook":
            await run_webhook(bot, dp)
        else:
            await run_polling(bot, dp)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await close_db()
        log.info("Shut down cleanly")
