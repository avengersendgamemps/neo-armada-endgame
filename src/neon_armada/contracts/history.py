"""History file schema (``contracts/history-format.md``, version 1).

This module validates the structure of a decoded history document. It does not
read files, apply events or run game rules.
"""

from __future__ import annotations

import re
from typing import Any

from neon_armada.contracts.models import (
    EXCLUSION_REASONS,
    INVALID_REASONS,
    ContractError,
    MatchConfig,
    MatchResult,
    MatchState,
    StaticMap,
    require_int,
    require_key,
    require_list,
    require_mapping,
)
from neon_armada.contracts.versions import HISTORY_VERSION

HISTORY_FORMAT = "neon-armada-history"
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")

# Event type -> required integer fields (``reason`` is validated separately).
EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "timeout": ("player", "consecutive"),
    "malformed_response": ("player",),
    "agent_excluded": ("player",),
    "invalid_command": ("player",),
    "ship_spawned": ("player", "ship", "x", "y"),
    "build_started": ("player", "cost"),
    "ship_moved": ("ship", "x", "y"),
    "collision": ("x", "y", "energy_added"),
    "mined": ("ship", "amount"),
    "delivered": ("ship", "amount"),
}
_REASONS = {"agent_excluded": EXCLUSION_REASONS, "invalid_command": INVALID_REASONS}


class HistoryError(ContractError):
    """A history document is corrupt, incomplete or of an unsupported version."""


def validate_event(event: Any, where: str) -> None:
    """Validate one history event object."""
    event = require_mapping(event, where)
    kind = event.get("type")
    if kind not in EVENT_FIELDS:
        raise HistoryError(f"{where}: unknown event type {kind!r}")
    for name in EVENT_FIELDS[kind]:
        value = require_int(require_key(event, name, where), f"{where}.{name}", 0)
        if name == "player" and value > 1:
            raise HistoryError(f"{where}.player must be 0 or 1")
    if kind in _REASONS and event.get("reason") not in _REASONS[kind]:
        raise HistoryError(f"{where}: unknown reason {event.get('reason')!r}")
    if kind == "invalid_command" and "ship" in event:
        require_int(event["ship"], f"{where}.ship", 0)
    if kind == "collision":
        ships = require_list(require_key(event, "ships", where), f"{where}.ships")
        if len(ships) < 2:
            raise HistoryError(f"{where}.ships must list at least two ships")
        for ship in ships:
            require_int(ship, f"{where}.ships[]", 0)


def _fingerprint(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _FINGERPRINT.match(value):
        raise HistoryError(f"{where} must be 64 lowercase hexadecimal characters")
    return value


def validate_history_document(document: Any) -> None:
    """Validate the structure of a decoded history document.

    Raises :class:`HistoryError` describing the first problem found.
    """
    try:
        _validate(document)
    except HistoryError:
        raise
    except ContractError as error:
        raise HistoryError(str(error)) from error


def _validate(document: Any) -> None:
    doc = require_mapping(document, "history")
    if doc.get("format") != HISTORY_FORMAT:
        raise HistoryError(f"history.format must be {HISTORY_FORMAT!r}")
    version = doc.get("history_version")
    if version != HISTORY_VERSION or isinstance(version, bool):
        raise HistoryError(f"unsupported history_version: {version!r}")

    header = require_mapping(require_key(doc, "header", "history"), "header")
    for name in ("models_version", "protocol_version", "generator_version"):
        require_int(require_key(header, name, "header"), f"header.{name}", 1)
    for name in ("seed", "map_seed", "map_attempt"):
        require_int(require_key(header, name, "header"), f"header.{name}", 0)
    config = MatchConfig.from_dict(require_key(header, "config", "header"))
    agents = require_list(require_key(header, "agents", "header"), "header.agents", 2)
    for player, agent in enumerate(agents):
        agent = require_mapping(agent, f"header.agents[{player}]")
        if agent.get("player_id") != player or not isinstance(agent.get("name"), str):
            raise HistoryError(f"header.agents[{player}] needs player_id and name")

    static_map = StaticMap.from_dict(require_key(doc, "map", "history"))
    if static_map.size != config.map_size:
        raise HistoryError("map.size does not match header.config.map_size")
    initial = MatchState.from_dict(require_key(doc, "initial_state", "history"))
    if initial.tick != 0:
        raise HistoryError("initial_state.tick must be 0")
    _fingerprint(require_key(doc, "initial_fingerprint", "history"), "fingerprint")

    setup = require_list(require_key(doc, "setup_events", "history"), "setup_events")
    for index, event in enumerate(setup):
        validate_event(event, f"setup_events[{index}]")

    ticks = require_list(require_key(doc, "ticks", "history"), "history.ticks")
    for index, entry in enumerate(ticks):
        where = f"ticks[{index}]"
        entry = require_mapping(entry, where)
        if require_key(entry, "tick", where) != index + 1:
            raise HistoryError(f"{where}.tick must be {index + 1}")
        events = require_list(require_key(entry, "events", where), f"{where}.events")
        for event_index, event in enumerate(events):
            validate_event(event, f"{where}.events[{event_index}]")
        _fingerprint(require_key(entry, "fingerprint", where), f"{where}.fingerprint")

    result = MatchResult.from_dict(require_key(doc, "result", "history"))
    if result.ticks_played != len(ticks):
        raise HistoryError("result.ticks_played does not match the number of ticks")
