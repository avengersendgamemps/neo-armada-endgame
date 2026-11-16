"""Shared pytest helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

# GUI tests run without a display; must be set before PySide6 is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def load_fixture():
    """Return a loader for JSON fixtures under ``tests/fixtures``."""

    def load(relative: str) -> Any:
        return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))

    return load


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole test session (offscreen)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
