"""Shared pytest helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def load_fixture():
    """Return a loader for JSON fixtures under ``tests/fixtures``."""

    def load(relative: str) -> Any:
        return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))

    return load
