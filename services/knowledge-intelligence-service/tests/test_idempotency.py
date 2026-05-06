from __future__ import annotations

import pytest

from src.core.errors import KISError
from src.core.idempotency import acquire_idempotency, complete_idempotency, idempotent_response


def test_idempotency_replay_returns_stored_response_for_same_body() -> None:
    first = acquire_idempotency("idem-1", body={"name": "A"}, domain_id="d1", actor_id="svc")
    complete_idempotency("idem-1", {"id": "created"})
    second = acquire_idempotency("idem-1", body={"name": "A"}, domain_id="d1", actor_id="svc")

    assert first["status"] == "new"
    assert second["status"] == "replay"
    assert idempotent_response("idem-1") == {"id": "created"}


def test_idempotency_conflict_for_same_key_different_body() -> None:
    acquire_idempotency("idem-1", body={"name": "A"}, domain_id="d1", actor_id="svc")

    with pytest.raises(KISError) as error:
        acquire_idempotency("idem-1", body={"name": "B"}, domain_id="d1", actor_id="svc")

    assert error.value.code == "IDEMPOTENCY_CONFLICT"
