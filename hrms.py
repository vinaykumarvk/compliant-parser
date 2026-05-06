from __future__ import annotations

"""HRMS authentication/profile adapter.

Production can configure ``HRMS_AUTH_URL`` to authenticate against a REST
endpoint.  When it is absent, callers can fall back to the local user table,
which keeps development and tests self-contained.
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class HRMSProfile:
    employee_id: str
    full_name: str
    rank: Optional[str]
    designation: Optional[str]
    police_station_id: Optional[str]
    role: str


def _post_auth(url: str, employee_id: str, password: str, timeout_seconds: float) -> Optional[dict[str, Any]]:
    payload = json.dumps({"employee_id": employee_id, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if response.status in (401, 403):
            return None
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


async def authenticate_hrms(employee_id: str, password: str) -> Optional[HRMSProfile]:
    """Authenticate against HRMS and return a synced profile.

    ``None`` means either HRMS is not configured or the credentials were not
    accepted.  The API layer decides whether to fall back to local auth.
    """
    url = os.getenv("HRMS_AUTH_URL", "").strip()
    if not url:
        return None

    try:
        data = await asyncio.to_thread(_post_auth, url, employee_id, password, 10.0)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if not data or data.get("authenticated") is False:
        return None

    role = data.get("role") or "IO"
    return HRMSProfile(
        employee_id=data.get("employee_id") or employee_id,
        full_name=data.get("full_name") or data.get("name") or employee_id,
        rank=data.get("rank"),
        designation=data.get("designation") or data.get("posting"),
        police_station_id=data.get("police_station_id"),
        role=role,
    )
