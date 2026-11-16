"""Serialise a finished match into a history document and write it to disk.

Format: ``contracts/history-format.md`` version 1. Only deterministic match
data is written; timing, paths and process details are not.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from neon_armada.contracts.history import HISTORY_FORMAT
from neon_armada.contracts.versions import (
    GENERATOR_VERSION,
    HISTORY_VERSION,
    MODELS_VERSION,
    PROTOCOL_VERSION,
)
from neon_armada.engine.match import MatchRecord


def record_to_document(record: MatchRecord) -> dict[str, Any]:
    """Return the JSON-compatible history document for ``record``."""
    return {
        "format": HISTORY_FORMAT,
        "history_version": HISTORY_VERSION,
        "header": {
            "models_version": MODELS_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "generator_version": GENERATOR_VERSION,
            "seed": record.seed,
            "map_seed": record.map_seed,
            "map_attempt": record.map_attempt,
            "config": record.config.to_dict(),
            "agents": [
                {"player_id": player, "name": name}
                for player, name in enumerate(record.agent_names)
            ],
        },
        "map": record.static_map.to_dict(),
        "initial_state": record.initial_state.to_dict(),
        "initial_fingerprint": record.initial_fingerprint,
        "setup_events": list(record.setup_events),
        "ticks": [
            {
                "tick": tick.tick,
                "events": list(tick.events),
                "fingerprint": tick.fingerprint,
            }
            for tick in record.ticks
        ],
        "result": record.result.to_dict(),
    }


def write_history(record: MatchRecord, path: Path) -> None:
    """Write the history of ``record`` to ``path`` atomically.

    Parent directories are created and an existing file is replaced. The data
    goes to a temporary sibling first, so readers never see a partial file.
    Raises ``OSError`` if the file cannot be written.
    """
    document = record_to_document(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, separators=(",", ":"), ensure_ascii=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
