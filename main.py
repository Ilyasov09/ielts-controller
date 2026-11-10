"""IELTS Controller — Telegram bot.

Ishga tushirish:        python main.py
Sozlamalarni qayta:     python main.py --setup

.env yo‘q bo‘lsa, birinchi ishga tushirishda terminalda sozlash savollari beriladi.
"""
from __future__ import annotations

import asyncio
import logging
import sys

if sys.version_info < (3, 9):  # aiogram 3 talabi
    sys.exit("IELTS Controller uchun Python 3.9 yoki undan yangi versiya kerak.")

if __name__ == "__main__":
    # config import qilinishidan OLDIN — .env shu yerda yaratiladi
    from utils.env_setup import ensure_env

    ensure_env(force="--setup" in sys.argv[1:])

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from config import config
from database.database import DbSessionMiddleware, close_db, init_db
from handlers import get_routers
from services.access import AccessMiddleware
from services.scheduler import BotScheduler

log = logging.getLogger("ielts_controller")

COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish / sozlash"),
    BotCommand(command="menu", description="Asosiy menyu"),
    BotCommand(command="daily", description="📚 Daily Report"),
    BotCommand(command="stats", description="📊 Statistics"),
    BotCommand(command="countdown", description="⏳ Exam Countdown"),
    BotCommand(command="streak", description="🔥 Streak"),
    BotCommand(command="history", description="🗂 History"),
    BotCommand(command="planner", description="🎯 Study Planner"),
    BotCommand(command="poll", description="🗳 Yangi poll yaratish"),
    BotCommand(command="polls", description="📊 Polllar: natija va yopish"),
    BotCommand(command="broadcast", description="📢 Broadcast rejimi"),
    BotCommand(command="export", description="📤 PDF / Excel hisobot"),
    BotCommand(command="settings", description="⚙️ Sozlamalar"),
    BotCommand(command="cancel", description="❌ Joriy amalni bekor qilish"),
]


def build_dispatcher(scheduler: BotScheduler) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.message.outer_middleware(AccessMiddleware())
    dp.callback_query.outer_middleware(AccessMiddleware())
    dp.include_routers(*get_routers())
    dp["scheduler"] = scheduler
    return dp


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    if not config.bot_token:
        sys.exit("BOT_TOKEN topilmadi. .env faylini to‘ldiring (namuna: .env.example).")

    await init_db()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    scheduler = BotScheduler(bot)
    dp = build_dispatcher(scheduler)

    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            sys.exit("BOT_TOKEN noto‘g‘ri yoki bekor qilingan. Yangilash: python main.py --setup")
        log.info("Bot: @%s | Python %s | TZ %s", me.username, sys.version.split()[0], config.timezone)
        await bot.set_my_commands(COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.delete_webhook(drop_pending_updates=False)
        await scheduler.start()
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code not in (None, 0):
            raise
