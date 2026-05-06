from __future__ import annotations

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]

for path in (SERVICE_ROOT, REPO_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

import pytest

from src.state import STORE


@pytest.fixture(autouse=True)
def reset_store():
    STORE.reset()
    yield
    STORE.reset()
