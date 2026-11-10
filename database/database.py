"""Bazaga ulanish va sessiya middleware."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import config

IS_SQLITE = config.database_url.startswith("sqlite")

engine = create_async_engine(
    config.database_url,
    pool_pre_ping=not IS_SQLITE,
    # SQLite: bir vaqtda yozishda "database is locked" bo‘lmasligi uchun kutish
    connect_args={"timeout": 30} if IS_SQLITE else {},
)

if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")   # o‘qish va yozish bir-birini to‘smaydi
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    from database.migrations import run_migrations

    await run_migrations(engine)


async def close_db() -> None:
    await engine.dispose()


class DbSessionMiddleware(BaseMiddleware):
    """Har bir update uchun alohida sessiya ochadi va handlerga `session` sifatida beradi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            data["session"] = session
            return await handler(event, data)
