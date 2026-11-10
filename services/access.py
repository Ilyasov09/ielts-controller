"""Admin aniqlash va kirishni cheklash."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.repository import get_settings

log = logging.getLogger(__name__)

_owner_id: Optional[int] = None
_owner_loaded = False

# Bu prefiksli callbacklar hamma uchun ochiq (kanaldagi poll ovozlari)
PUBLIC_CALLBACK_PREFIXES = ("pv:",)


async def _get_owner(session: AsyncSession) -> Optional[int]:
    global _owner_id, _owner_loaded
    if not _owner_loaded:
        settings = await get_settings(session)
        _owner_id = settings.owner_id
        _owner_loaded = True
    return _owner_id


async def get_admin_ids(session: AsyncSession) -> Set[int]:
    ids = set(config.admin_ids)
    owner = await _get_owner(session)
    if owner:
        ids.add(owner)
    return ids


async def is_admin(user_id: int, session: AsyncSession) -> bool:
    if user_id in config.admin_ids:
        return True
    return user_id == await _get_owner(session)


async def claim_owner(user_id: int, session: AsyncSession) -> bool:
    """ADMIN_IDS berilmagan bo‘lsa — botga birinchi /start bosgan odam egasi bo‘ladi."""
    global _owner_id, _owner_loaded
    if config.admin_ids:
        return False
    settings = await get_settings(session)
    if settings.owner_id is None:
        settings.owner_id = user_id
        await session.commit()
        log.warning("Bot egasi sifatida belgilandi: %s", user_id)
    _owner_id = settings.owner_id
    _owner_loaded = True
    return settings.owner_id == user_id


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]

        if isinstance(event, CallbackQuery):
            if event.data and event.data.startswith(PUBLIC_CALLBACK_PREFIXES):
                return await handler(event, data)
            if await is_admin(event.from_user.id, session):
                return await handler(event, data)
            await event.answer("⛔ Bu tugma faqat admin uchun.")
            return None

        if isinstance(event, Message):
            if event.chat.type != "private" or event.from_user is None:
                return None
            user_id = event.from_user.id
            if await is_admin(user_id, session):
                return await handler(event, data)
            if (event.text or "").startswith("/start") and await claim_owner(user_id, session):
                return await handler(event, data)
            await event.answer(
                "⛔ Bu shaxsiy bot, sizda kirish huquqi yo‘q.\n"
                "Sizning Telegram ID: <code>%d</code>" % user_id
            )
            return None

        return await handler(event, data)
