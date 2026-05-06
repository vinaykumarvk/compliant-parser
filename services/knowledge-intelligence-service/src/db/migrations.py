from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from src.db.models import Base


async def run_migrations(engine: AsyncEngine) -> None:
    """Create the MVP schema idempotently.

    Production deployments should replace this helper with Alembic migrations.
    The MVP keeps table creation local and repeatable for tests and dev harnesses.
    """
    # Import model modules so all tables are registered on the shared Base metadata.
    from src.db import data_models as _data_models  # noqa: F401
    from src.db import knowledge_models as _knowledge_models  # noqa: F401
    from src.db import reasoning_models as _reasoning_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
