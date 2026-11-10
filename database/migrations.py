"""Oddiy avtomatik migratsiya.

1. Yo‘q jadvallarni yaratadi.
2. Mavjud jadvalga keyinchalik qo‘shilgan ustunlarni (ALTER TABLE ... ADD COLUMN) qo‘shadi.

Ustunni o‘chirish yoki turini o‘zgartirish kerak bo‘lsa — Alembic ishlatish tavsiya etiladi.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, literal, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from database.models import Base

log = logging.getLogger(__name__)


def _add_missing_columns(conn: Connection) -> None:
    inspector = inspect(conn)
    preparer = conn.dialect.identifier_preparer
    for table in Base.metadata.sorted_tables:
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(dialect=conn.dialect)
            ddl = "ALTER TABLE %s ADD COLUMN %s %s" % (
                preparer.quote(table.name),
                preparer.quote(column.name),
                col_type,
            )
            default = column.default
            if default is not None and getattr(default, "is_scalar", False):
                rendered = literal(default.arg, type_=column.type).compile(
                    dialect=conn.dialect, compile_kwargs={"literal_binds": True}
                )
                ddl += " DEFAULT %s" % rendered
                if not column.nullable:
                    ddl += " NOT NULL"
            log.warning("Migratsiya: %s", ddl)
            conn.execute(text(ddl))


async def run_migrations(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
