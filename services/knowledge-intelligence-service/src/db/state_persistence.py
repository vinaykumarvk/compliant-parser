from __future__ import annotations

from sqlalchemy import select

from src.config import Settings
from src.db.models import KISStateSnapshot
from src.db.session import get_session_factory, is_database_configured
from src.state import STORE


SNAPSHOT_ID = "default"


async def hydrate_store(settings: Settings) -> bool:
    if not is_database_configured(settings):
        return False
    session_factory = await get_session_factory(settings)
    async with session_factory() as session:
        row = await session.get(KISStateSnapshot, SNAPSHOT_ID)
        if row is None:
            return False
        STORE.import_payload(row.payload)
        return True


async def persist_store(settings: Settings) -> bool:
    if not is_database_configured(settings):
        return False
    session_factory = await get_session_factory(settings)
    async with session_factory() as session:
        row = await session.get(KISStateSnapshot, SNAPSHOT_ID)
        payload = STORE.export_payload()
        if row is None:
            session.add(KISStateSnapshot(id=SNAPSHOT_ID, payload=payload))
        else:
            row.payload = payload
        await session.commit()
        return True


async def has_persisted_state(settings: Settings) -> bool:
    if not is_database_configured(settings):
        return False
    session_factory = await get_session_factory(settings)
    async with session_factory() as session:
        result = await session.execute(select(KISStateSnapshot.id).where(KISStateSnapshot.id == SNAPSHOT_ID))
        return result.scalar_one_or_none() is not None
