from __future__ import annotations

from src.config import Settings
from src.db.session import database_url_status, normalize_database_url
from src.db import state_persistence
from src.state import STORE


class _ScalarResult:
    def scalar_one_or_none(self):
        return state_persistence.SNAPSHOT_ID


class _FakeSession:
    def __init__(self, rows: dict) -> None:
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def get(self, _model, row_id: str):
        return self.rows.get(row_id)

    def add(self, row) -> None:
        self.rows[row.id] = row

    async def commit(self) -> None:
        return None

    async def execute(self, _stmt):
        return _ScalarResult()


def test_kis_store_persists_and_hydrates_through_db_session(monkeypatch) -> None:
    settings = Settings(database_url="postgresql+asyncpg://example")
    rows: dict = {}

    async def fake_session_factory(_settings):
        return lambda: _FakeSession(rows)

    monkeypatch.setattr(state_persistence, "is_database_configured", lambda _settings: True)
    monkeypatch.setattr(state_persistence, "get_session_factory", fake_session_factory)

    STORE.domains["police-iqw"] = {"id": "police-iqw", "name": "Police IQW"}

    persisted = __import__("asyncio").run(state_persistence.persist_store(settings))
    STORE.reset()
    hydrated = __import__("asyncio").run(state_persistence.hydrate_store(settings))

    assert persisted is True
    assert hydrated is True
    assert STORE.domains["police-iqw"]["name"] == "Police IQW"


def test_deployed_postgresql_url_is_normalized_without_exposing_password() -> None:
    url = "postgresql://puda:secret@/police_kb?host=/cloudsql/policing-apps:asia-southeast1:policing-db-v2"

    normalized = normalize_database_url(url)
    status = database_url_status(url)

    assert normalized.startswith("postgresql+asyncpg://")
    assert status == {
        "scheme": "postgresql+asyncpg",
        "user": "puda",
        "database": "police_kb",
        "password_configured": True,
    }
    assert "secret" not in str(status)


def test_settings_accepts_deployed_database_url_env(monkeypatch) -> None:
    monkeypatch.delenv("KIS_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://puda:secret@/police_kb?host=/cloudsql/policing-apps:asia-southeast1:policing-db-v2",
    )

    settings = Settings.from_env()

    assert settings.database_url.startswith("postgresql://puda:")
    assert "police_kb" in settings.database_url
