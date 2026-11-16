"""History reader, event-based reconstruction and determinism comparison.

Everything here follows ``contracts/history-format.md`` version 1 and is
shared by the engine's verifier and the desktop client. A match is rebuilt
purely from the recorded initial state and events: no game rule, agent or
engine code is involved, only the normative "state effect" of each event.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.history import HistoryError, validate_history_document
from neon_armada.contracts.models import (
    SHIP_CAPACITY,
    ContractError,
    EnergyCell,
    MatchConfig,
    MatchResult,
    MatchState,
    Ship,
    StaticMap,
)

Event = dict[str, Any]


@dataclass(frozen=True, slots=True)
class HistoryTick:
    """Recorded data of one tick."""

    tick: int
    events: tuple[Event, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class History:
    """A validated, typed match history."""

    seed: int
    map_seed: int
    map_attempt: int
    config: MatchConfig
    agent_names: tuple[str, str]
    static_map: StaticMap
    initial_state: MatchState
    initial_fingerprint: str
    setup_events: tuple[Event, ...]
    ticks: tuple[HistoryTick, ...]
    result: MatchResult


@dataclass(frozen=True, slots=True)
class Comparison:
    """Outcome of comparing two histories for determinism."""

    identical: bool
    first_divergent_tick: int | None
    detail: str


def parse_history(document: Any) -> History:
    """Validate a decoded history document and convert it to :class:`History`."""
    validate_history_document(document)
    header = document["header"]
    return History(
        seed=header["seed"],
        map_seed=header["map_seed"],
        map_attempt=header["map_attempt"],
        config=MatchConfig.from_dict(header["config"]),
        agent_names=(header["agents"][0]["name"], header["agents"][1]["name"]),
        static_map=StaticMap.from_dict(document["map"]),
        initial_state=MatchState.from_dict(document["initial_state"]),
        initial_fingerprint=document["initial_fingerprint"],
        setup_events=tuple(document["setup_events"]),
        ticks=tuple(
            HistoryTick(entry["tick"], tuple(entry["events"]), entry["fingerprint"])
            for entry in document["ticks"]
        ),
        result=MatchResult.from_dict(document["result"]),
    )


def load_history(path: str | Path) -> History:
    """Read and validate a history file.

    Raises :class:`HistoryError` if the file is missing, unreadable, not valid
    JSON (corrupt or truncated), of an unsupported version or malformed.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise HistoryError(f"cannot read history file {path}: {error}") from error
    try:
        document = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as error:
        raise HistoryError(f"history file {path} is not valid JSON: {error}") from error
    return parse_history(document)


def apply_events(state: MatchState, events: Sequence[Event], tick: int) -> MatchState:
    """Return the state after applying one tick's events to ``state``.

    Implements the "state effect" column of the history contract. Raises
    :class:`HistoryError` when an event cannot be applied (for example it
    names a ship that does not exist).
    """
    ships = {ship.id: ship for ship in state.ships}
    energy = {(cell.x, cell.y): cell.energy for cell in state.energy}
    reserves = list(state.reserves)
    budgets = list(state.move_budgets)
    pending = list(state.pending_builds)
    invalid = list(state.invalid_commands)
    next_ship_id = state.next_ship_id

    def ship_of(event: Event) -> Ship:
        ship = ships.get(event["ship"])
        if ship is None:
            raise HistoryError(f"tick {tick}: event names unknown ship {event['ship']}")
        return ship

    for event in events:
        kind = event["type"]
        if kind in ("malformed_response", "invalid_command"):
            invalid[event["player"]] += 1
        elif kind == "ship_spawned":
            if event["ship"] in ships:
                raise HistoryError(f"tick {tick}: ship {event['ship']} spawned twice")
            ships[event["ship"]] = Ship(
                event["ship"], event["player"], event["x"], event["y"], 0
            )
            pending[event["player"]] = False
            next_ship_id = event["ship"] + 1
        elif kind == "build_started":
            reserves[event["player"]] -= event["cost"]
            pending[event["player"]] = True
        elif kind == "ship_moved":
            ship = ship_of(event)
            ships[ship.id] = Ship(
                ship.id, ship.owner, event["x"], event["y"], ship.cargo
            )
            budgets[ship.owner] -= 1
        elif kind == "collision":
            for ship_id in event["ships"]:
                if ships.pop(ship_id, None) is None:
                    raise HistoryError(f"tick {tick}: collision of unknown ship")
            if event["energy_added"]:
                cell = (event["x"], event["y"])
                energy[cell] = energy.get(cell, 0) + event["energy_added"]
        elif kind == "mined":
            ship = ship_of(event)
            cell = (ship.x, ship.y)
            remaining = energy.get(cell, 0) - event["amount"]
            if remaining < 0:
                raise HistoryError(f"tick {tick}: mined more than the cell holds")
            if remaining:
                energy[cell] = remaining
            else:
                energy.pop(cell, None)
            ships[ship.id] = Ship(
                ship.id, ship.owner, ship.x, ship.y, ship.cargo + event["amount"]
            )
        elif kind == "delivered":
            ship = ship_of(event)
            reserves[ship.owner] += event["amount"]
            ships[ship.id] = Ship(ship.id, ship.owner, ship.x, ship.y, 0)
        # "timeout" and "agent_excluded" have no state effect.

    if min(reserves) < 0 or min(budgets) < 0:
        raise HistoryError(f"tick {tick}: negative reserve or movement budget")
    if any(ship.cargo > SHIP_CAPACITY for ship in ships.values()):
        raise HistoryError(f"tick {tick}: ship cargo above capacity")
    try:
        return MatchState(
            tick=tick,
            reserves=(reserves[0], reserves[1]),
            move_budgets=(budgets[0], budgets[1]),
            pending_builds=(pending[0], pending[1]),
            invalid_commands=(invalid[0], invalid[1]),
            next_ship_id=next_ship_id,
            ships=tuple(ships[ship_id] for ship_id in sorted(ships)),
            energy=tuple(
                EnergyCell(x, y, amount)
                for (x, y), amount in sorted(
                    energy.items(), key=lambda item: (item[0][1], item[0][0])
                )
            ),
        )
    except ContractError as error:
        raise HistoryError(f"tick {tick}: inconsistent state: {error}") from error


def reconstruct_states(history: History) -> list[MatchState]:
    """Return every state of the match: index ``t`` is the state after tick ``t``.

    Index 0 is the initial state. Only recorded events are used.
    """
    states = [history.initial_state]
    for entry in history.ticks:
        states.append(apply_events(states[-1], entry.events, entry.tick))
    return states


def first_invalid_tick(history: History) -> int | None:
    """Reconstruct the match and check every state against its fingerprint.

    Returns ``None`` if all fingerprints match, ``0`` if the initial state does
    not match ``initial_fingerprint``, otherwise the first tick whose
    reconstructed state differs from the recorded fingerprint (or cannot be
    reconstructed at all).
    """
    if state_fingerprint(history.initial_state) != history.initial_fingerprint:
        return 0
    state = history.initial_state
    for entry in history.ticks:
        try:
            state = apply_events(state, entry.events, entry.tick)
        except HistoryError:
            return entry.tick
        if state_fingerprint(state) != entry.fingerprint:
            return entry.tick
    return None


def compare_histories(first: History, second: History) -> Comparison:
    """Compare two histories for determinism (history contract §5).

    Agent names are ignored. The result names the first divergent tick: ``0``
    when seed, configuration, map or initial state already differ.
    """
    for name in ("seed", "config", "static_map", "initial_fingerprint"):
        if getattr(first, name) != getattr(second, name):
            return Comparison(False, 0, f"{name} differs")
    for one, two in zip(first.ticks, second.ticks, strict=False):
        if one.fingerprint != two.fingerprint:
            return Comparison(False, one.tick, "fingerprint mismatch")
    if len(first.ticks) != len(second.ticks):
        shorter = min(len(first.ticks), len(second.ticks))
        return Comparison(False, shorter + 1, "one match ended earlier")
    return Comparison(True, None, "identical")
