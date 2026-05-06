from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Optional

from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config import Settings, get_settings

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None
_connector: Any = None
_engine_key: Optional[str] = None

_POOL_KWARGS = dict(pool_size=5, max_overflow=2, pool_recycle=1800, pool_pre_ping=True)


def get_engine(settings: Optional[Settings] = None) -> Optional[AsyncEngine]:
    global _connector, _engine, _engine_key, _sessionmaker
    settings = settings or get_settings()
    configured_key = settings.database_url or settings.cloud_sql_connection_name
    if not configured_key:
        return None
    engine_key = "|".join(
        [
            settings.database_url or "",
            settings.cloud_sql_connection_name or "",
            settings.db_user,
            settings.db_name,
        ]
    )
    if _engine is not None and _engine_key == engine_key:
        return _engine
    if _engine is not None:
        raise RuntimeError("KIS database engine is already initialized with different settings.")

    if settings.database_url:
        database_url = normalize_database_url(settings.database_url)
        _engine = create_async_engine(database_url, **_pool_kwargs_for_url(database_url))
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
        _engine_key = engine_key
        return _engine

    from google.cloud.sql.connector import Connector

    _connector = Connector()

    async def get_connection():
        kwargs: dict[str, Any] = {"user": settings.db_user, "db": settings.db_name}
        if settings.db_iam_auth and not settings.db_password:
            kwargs["enable_iam_auth"] = True
        elif settings.db_password:
            kwargs["password"] = settings.db_password
        return await _connector.connect_async(
            settings.cloud_sql_connection_name,
            "asyncpg",
            **kwargs,
        )

    _engine = create_async_engine(
        "postgresql+asyncpg://",
        async_creator=get_connection,
        **_POOL_KWARGS,
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    _engine_key = engine_key
    return _engine


def _pool_kwargs_for_url(database_url: str) -> dict[str, Any]:
    if database_url.startswith("sqlite"):
        return {"pool_pre_ping": True}
    return dict(_POOL_KWARGS)


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


def database_url_status(database_url: str) -> dict[str, Any]:
    normalized = normalize_database_url(database_url)
    parsed = urlparse(normalized)
    return {
        "scheme": parsed.scheme,
        "user": parsed.username,
        "database": (parsed.path or "").lstrip("/") or None,
        "password_configured": bool(parsed.password),
    }


def is_database_configured(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.database_url or settings.cloud_sql_connection_name)


async def get_session_factory(settings: Optional[Settings] = None) -> async_sessionmaker[AsyncSession]:
    engine = get_engine(settings)
    if engine is None or _sessionmaker is None:
        raise RuntimeError("KIS database is not configured")
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    engine = get_engine()
    if engine is None or _sessionmaker is None:
        raise RuntimeError("KIS database is not configured")
    async with _sessionmaker() as session:
        yield session


async def database_status(settings: Optional[Settings] = None) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = get_engine(settings)
    if engine is None:
        return {
            "configured": False,
            "status": "not_configured",
            "connection": "none",
        }
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        return {
            "configured": True,
            "status": "ok",
            "connection": "cloud_sql" if settings.cloud_sql_connection_name and not settings.database_url else "direct_url",
            "database": (
                settings.db_name
                if settings.cloud_sql_connection_name and not settings.database_url
                else database_url_status(settings.database_url)["database"]
                if settings.database_url
                else None
            ),
        }
    except Exception as exc:
        return {
            "configured": True,
            "status": "error",
            "connection": "cloud_sql" if settings.cloud_sql_connection_name and not settings.database_url else "direct_url",
            "error_type": exc.__class__.__name__,
        }


async def dispose_engine() -> None:
    global _connector, _engine, _engine_key, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    if _connector is not None:
        if hasattr(_connector, "close_async"):
            await _connector.close_async()
        elif hasattr(_connector, "close"):
            _connector.close()
    _engine = None
    _connector = None
    _engine_key = None
    _sessionmaker = None
