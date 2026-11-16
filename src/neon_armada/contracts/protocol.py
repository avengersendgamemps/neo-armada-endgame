"""Engine–agent protocol messages (``contracts/agent-protocol.md``, version 1).

Pure serialisation and parsing helpers. Process handling lives in the engine's
agent runtime; nothing here touches pipes or subprocesses.
"""

from __future__ import annotations

import json
from typing import Any

from neon_armada.contracts.models import (
    Action,
    ContractError,
    MatchConfig,
    MatchResult,
    MatchState,
    PlayerCommands,
    ShipCommand,
    StaticMap,
    require_int,
    require_key,
    require_list,
    require_mapping,
)
from neon_armada.contracts.versions import PROTOCOL_VERSION

MAX_AGENT_LINE_BYTES = 65_536
MAX_CONSECUTIVE_TIMEOUTS = 3
END_REASON_VALUES = ("finished", "excluded", "error")
_ACTIONS = {action.value: action for action in Action}


class ProtocolError(ContractError):
    """An agent message violates the protocol (the response is malformed)."""


class StaleResponseError(ProtocolError):
    """A ``commands`` message answers an earlier tick and must be discarded."""


def encode_message(message: dict[str, Any]) -> str:
    """Encode one protocol message as a single JSON line ending in ``\\n``."""
    return json.dumps(message, separators=(",", ":"), ensure_ascii=True) + "\n"


def init_message(
    player_id: int, config: MatchConfig, static_map: StaticMap
) -> dict[str, Any]:
    """Build the ``init`` message with the static map for one player."""
    return {
        "type": "init",
        "protocol_version": PROTOCOL_VERSION,
        "player_id": require_int(player_id, "player_id", 0, 1),
        "config": config.to_dict(),
        "map": static_map.to_dict(),
    }


def tick_message(state: MatchState) -> dict[str, Any]:
    """Build the ``tick`` message that asks for the commands of the next tick."""
    return {
        "type": "tick",
        "tick": state.tick + 1,
        "reserves": list(state.reserves),
        "move_budgets": list(state.move_budgets),
        "pending_builds": list(state.pending_builds),
        "ships": [ship.to_dict() for ship in state.ships],
        "energy": [cell.to_list() for cell in state.energy],
    }


def end_message(reason: str, result: MatchResult | None = None) -> dict[str, Any]:
    """Build the ``end`` message."""
    if reason not in END_REASON_VALUES:
        raise ContractError(f"end.reason is unknown: {reason!r}")
    message: dict[str, Any] = {"type": "end", "reason": reason}
    if reason == "finished":
        if result is None:
            raise ContractError("end message with reason 'finished' needs a result")
        message["winner"] = result.winner
        message["scores"] = list(result.scores)
    return message


def _decode_object(line: str | bytes) -> dict[str, Any]:
    if isinstance(line, bytes):
        if len(line) > MAX_AGENT_LINE_BYTES:
            raise ProtocolError("line exceeds the maximum agent line length")
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ProtocolError("line is not valid UTF-8") from error
    elif len(line.encode("utf-8")) > MAX_AGENT_LINE_BYTES:
        raise ProtocolError("line exceeds the maximum agent line length")
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ProtocolError("line is not valid JSON") from error
    if not isinstance(data, dict):
        raise ProtocolError("message must be a JSON object")
    return data


def _expect_type(data: dict[str, Any], expected: str) -> None:
    if data.get("type") != expected:
        raise ProtocolError(f"expected message type {expected!r}")


def parse_ready(line: str | bytes) -> None:
    """Validate a ``ready`` line; raise :class:`ProtocolError` if malformed."""
    data = _decode_object(line)
    _expect_type(data, "ready")
    if data.get("protocol_version") != PROTOCOL_VERSION or isinstance(
        data.get("protocol_version"), bool
    ):
        raise ProtocolError("unsupported or missing protocol_version")


def parse_commands(line: str | bytes, expected_tick: int) -> PlayerCommands:
    """Parse a ``commands`` line for ``expected_tick``.

    Raises :class:`StaleResponseError` for answers to earlier ticks and
    :class:`ProtocolError` for malformed responses. Individual malformed move
    entries do not fail the response; they are counted in
    ``PlayerCommands.malformed_entries``.
    """
    data = _decode_object(line)
    _expect_type(data, "commands")
    tick = data.get("tick")
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise ProtocolError("commands.tick must be an integer")
    if tick < expected_tick:
        raise StaleResponseError(f"stale commands for tick {tick}")
    if tick > expected_tick:
        raise ProtocolError(f"commands.tick {tick} is ahead of tick {expected_tick}")
    moves = data.get("moves")
    if not isinstance(moves, list):
        raise ProtocolError("commands.moves must be an array")
    build = data.get("build", False)
    if not isinstance(build, bool):
        raise ProtocolError("commands.build must be a boolean")

    parsed: list[ShipCommand] = []
    malformed = 0
    for entry in moves:
        ship = entry.get("ship") if isinstance(entry, dict) else None
        action = entry.get("action") if isinstance(entry, dict) else None
        if (
            isinstance(ship, bool)
            or not isinstance(ship, int)
            or ship < 0
            or not isinstance(action, str)
            or action not in _ACTIONS
        ):
            malformed += 1
            continue
        parsed.append(ShipCommand(ship=ship, action=_ACTIONS[action]))
    return PlayerCommands(moves=tuple(parsed), build=build, malformed_entries=malformed)


def parse_engine_message(line: str | bytes) -> dict[str, Any]:
    """Validate an engine→agent line (``init``, ``tick`` or ``end``).

    Used by tests and tooling to check that everything the engine sends
    conforms to the contract. Returns the decoded object.
    """
    data = _decode_object(line)
    kind = data.get("type")
    try:
        if kind == "init":
            if data.get("protocol_version") != PROTOCOL_VERSION:
                raise ProtocolError("unsupported protocol_version")
            require_int(require_key(data, "player_id", "init"), "init.player_id", 0, 1)
            MatchConfig.from_dict(require_key(data, "config", "init"))
            StaticMap.from_dict(require_key(data, "map", "init"))
        elif kind == "tick":
            tick = require_int(require_key(data, "tick", "tick"), "tick.tick", 1)
            state_like = dict(data)
            state_like["tick"] = tick - 1
            state_like.setdefault("invalid_commands", [0, 0])
            ships = require_list(require_key(data, "ships", "tick"), "tick.ships")
            highest = max(
                (require_mapping(s, "ship").get("id", 0) for s in ships), default=-1
            )
            state_like.setdefault("next_ship_id", require_int(highest, "ship.id") + 1)
            MatchState.from_dict(state_like)
        elif kind == "end":
            if data.get("reason") not in END_REASON_VALUES:
                raise ProtocolError("end.reason is unknown")
        else:
            raise ProtocolError(f"unknown message type: {kind!r}")
    except ProtocolError:
        raise
    except ContractError as error:
        raise ProtocolError(str(error)) from error
    return data
