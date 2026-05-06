from __future__ import annotations

"""CCTNS sync adapter for case metadata.

The production deployment can point ``CCTNS_SYNC_URL`` at a REST endpoint.  In
local/dev environments where that endpoint is not configured, sync requests are
left queued instead of blocking case creation.
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional


CCTNS_MAX_ATTEMPTS = 3
CCTNS_RETRY_INTERVAL_SECONDS = 30
CCTNS_UNAVAILABLE_MESSAGE = "CCTNS service unavailable. Sync queued for retry."


@dataclass(frozen=True)
class CCTNSSyncResult:
    status: str
    attempts: int
    cctns_case_id: Optional[str] = None
    queued: bool = False
    error: Optional[str] = None

    @property
    def retry_available(self) -> bool:
        return self.status in {"Pending", "Failed"}


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


async def sync_case_metadata(
    case_payload: dict[str, Any],
    *,
    max_attempts: int = CCTNS_MAX_ATTEMPTS,
    retry_interval_seconds: int = CCTNS_RETRY_INTERVAL_SECONDS,
    sleeper: Callable[[float], Any] = asyncio.sleep,
) -> CCTNSSyncResult:
    """Sync one case to CCTNS.

    Returns ``Pending`` when no integration URL is configured, ``Synced`` after
    a successful remote response, and ``Failed`` after the configured retry
    budget is exhausted.
    """
    url = os.getenv("CCTNS_SYNC_URL", "").strip()
    if not url:
        return CCTNSSyncResult(
            status="Pending",
            attempts=0,
            queued=True,
            error=CCTNS_UNAVAILABLE_MESSAGE,
        )

    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            response = await asyncio.to_thread(_post_json, url, case_payload, 10.0)
            cctns_case_id = response.get("cctns_case_id") or response.get("case_id")
            return CCTNSSyncResult(
                status="Synced",
                attempts=attempt,
                cctns_case_id=cctns_case_id,
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = str(exc)
            if attempt < max_attempts and retry_interval_seconds > 0:
                await sleeper(retry_interval_seconds)

    case_number = case_payload.get("crime_no") or case_payload.get("petition_no") or case_payload.get("id")
    return CCTNSSyncResult(
        status="Failed",
        attempts=max_attempts,
        queued=True,
        error=f"CCTNS sync failed for case {case_number} after {max_attempts} attempts. Manual retry available.",
    )
