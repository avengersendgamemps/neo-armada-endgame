"""Shared immutable domain models (``contracts/game-models.md``, version 1).

The models are plain values. They hold no behaviour beyond validation and
conversion to and from the JSON-compatible shapes used by the agent protocol
and the history format.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Official values (MPS Armada assignment, section "Mecanici Joc").
MIN_MAP_SIZE = 32
MAX_MAP_SIZE = 64
INITIAL_BASE_ENERGY = 1000
SHIP_CAPACITY = 100
BUILD_COST = 500
MINING_DIVISOR = 10
MAX_TICKS_LIMIT = 500

# Team decisions, not from the official spec (see contracts/game-models.md).
DEFAULT_MOVE_BUDGET = 1000
MAX_MOVE_BUDGET = 1_000_000
MAX_SEED = 2**64 - 1
PLAYER_COUNT = 2

CELL_EMPTY = "."
CELL_DEPOSIT = "*"
CELL_OBSTACLE = "#"
CELL_BASES = ("0", "1")
_CELL_CHARS = frozenset({CELL_EMPTY, CELL_DEPOSIT, CELL_OBSTACLE, *CELL_BASES})

INVALID_REASONS = (
    "out_of_bounds",
    "obstacle",
    "enemy_base",
    "no_budget",
    "unknown_ship",
    "duplicate_ship",
    "malformed_entry",
    "build_insufficient_energy",
    "build_already_pending",
)
EXCLUSION_REASONS = ("init_timeout", "init_failed", "timeout", "crashed")
END_REASONS = ("tick_limit", "budgets_exhausted")
DECIDED_BY = ("score", "ships_remaining", "carried_energy", "invalid_commands", "draw")


class ContractError(ValueError):
    """A value does not satisfy an integration contract."""


class Action(Enum):
    """Ship action. Moves consume one movement-budget unit; ``STAY`` is free."""

    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"
    STAY = "STAY"

    @property
    def delta(self) -> tuple[int, int]:
        """Return the ``(dx, dy)`` displacement of the action."""
        return _DELTAS[self]


_DELTAS = {
    Action.NORTH: (0, -1),
    Action.SOUTH: (0, 1),
    Action.EAST: (1, 0),
    Action.WEST: (-1, 0),
    Action.STAY: (0, 0),
}


def require_int(value: Any, name: str, low: int | None = None, high: int | None = None):
    """Return ``value`` if it is a non-boolean integer inside ``[low, high]``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{name} must be an integer")
    if low is not None and value < low:
        raise ContractError(f"{name} must be >= {low}, got {value}")
    if high is not None and value > high:
        raise ContractError(f"{name} must be <= {high}, got {value}")
    return value


def require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Return ``value`` if it is a JSON object."""
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def require_list(value: Any, name: str, length: int | None = None) -> Sequence[Any]:
    """Return ``value`` if it is a JSON array (optionally of a fixed length)."""
    if not isinstance(value, list | tuple):
        raise ContractError(f"{name} must be an array")
    if length is not None and len(value) != length:
        raise ContractError(f"{name} must have exactly {length} elements")
    return value


def require_key(data: Mapping[str, Any], key: str, owner: str) -> Any:
    """Return ``data[key]`` or raise a contract error naming the missing field."""
    if key not in data:
        raise ContractError(f"{owner}.{key} is missing")
    return data[key]


def _int_pair(value: Any, name: str, low: int | None = 0) -> tuple[int, int]:
    items = require_list(value, name, PLAYER_COUNT)
    return (
        require_int(items[0], f"{name}[0]", low),
        require_int(items[1], f"{name}[1]", low),
    )


def _bool_pair(value: Any, name: str) -> tuple[bool, bool]:
    items = require_list(value, name, PLAYER_COUNT)
    for index, item in enumerate(items):
        if not isinstance(item, bool):
            raise ContractError(f"{name}[{index}] must be a boolean")
    return (items[0], items[1])


@dataclass(frozen=True, slots=True)
class Ship:
    """A ship of one player."""

    id: int
    owner: int
    x: int
    y: int
    cargo: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "id": self.id,
            "owner": self.owner,
            "x": self.x,
            "y": self.y,
            "cargo": self.cargo,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Ship:
        data = require_mapping(data, "ship")
        return cls(
            id=require_int(require_key(data, "id", "ship"), "ship.id", 0),
            owner=require_int(require_key(data, "owner", "ship"), "ship.owner", 0, 1),
            x=require_int(require_key(data, "x", "ship"), "ship.x", 0),
            y=require_int(require_key(data, "y", "ship"), "ship.y", 0),
            cargo=require_int(
                require_key(data, "cargo", "ship"), "ship.cargo", 0, SHIP_CAPACITY
            ),
        )


@dataclass(frozen=True, slots=True)
class EnergyCell:
    """Energy currently held by one cell (only cells with energy > 0 are listed)."""

    x: int
    y: int
    energy: int

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.energy]

    @classmethod
    def from_list(cls, data: Any) -> EnergyCell:
        items = require_list(data, "energy entry", 3)
        return cls(
            x=require_int(items[0], "energy.x", 0),
            y=require_int(items[1], "energy.y", 0),
            energy=require_int(items[2], "energy.energy", 1),
        )


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """Match parameters. Limits without official numbers are team decisions."""

    map_size: int = MIN_MAP_SIZE
    max_ticks: int = MAX_TICKS_LIMIT
    move_budget: int = DEFAULT_MOVE_BUDGET
    tick_timeout_ms: int = 500
    init_timeout_ms: int = 3000
    memory_limit_mb: int = 512

    def __post_init__(self) -> None:
        require_int(self.map_size, "config.map_size", MIN_MAP_SIZE, MAX_MAP_SIZE)
        require_int(self.max_ticks, "config.max_ticks", 1, MAX_TICKS_LIMIT)
        require_int(self.move_budget, "config.move_budget", 0, MAX_MOVE_BUDGET)
        require_int(self.tick_timeout_ms, "config.tick_timeout_ms", 10, 60_000)
        require_int(self.init_timeout_ms, "config.init_timeout_ms", 10, 600_000)
        require_int(self.memory_limit_mb, "config.memory_limit_mb", 16, 65_536)

    def to_dict(self) -> dict[str, int]:
        return {
            "map_size": self.map_size,
            "max_ticks": self.max_ticks,
            "move_budget": self.move_budget,
            "tick_timeout_ms": self.tick_timeout_ms,
            "init_timeout_ms": self.init_timeout_ms,
            "memory_limit_mb": self.memory_limit_mb,
        }

    @classmethod
    def from_dict(cls, data: Any) -> MatchConfig:
        data = require_mapping(data, "config")
        names = (
            "map_size",
            "max_ticks",
            "move_budget",
            "tick_timeout_ms",
            "init_timeout_ms",
            "memory_limit_mb",
        )
        return cls(**{name: require_key(data, name, "config") for name in names})


@dataclass(frozen=True, slots=True)
class StaticMap:
    """Static part of the world: terrain and base positions."""

    size: int
    cells: tuple[str, ...]
    bases: tuple[tuple[int, int], tuple[int, int]]

    def __post_init__(self) -> None:
        require_int(self.size, "map.size", MIN_MAP_SIZE, MAX_MAP_SIZE)
        if len(self.cells) != self.size:
            raise ContractError(f"map.cells must have {self.size} rows")
        found: dict[str, tuple[int, int]] = {}
        for y, row in enumerate(self.cells):
            if not isinstance(row, str) or len(row) != self.size:
                raise ContractError(f"map.cells[{y}] must be a {self.size}-char string")
            for x, char in enumerate(row):
                if char not in _CELL_CHARS:
                    raise ContractError(f"map.cells[{y}][{x}] is not a cell: {char!r}")
                if char in CELL_BASES:
                    if char in found:
                        raise ContractError(f"map has more than one base {char!r}")
                    found[char] = (x, y)
        for player, char in enumerate(CELL_BASES):
            if found.get(char) != tuple(self.bases[player]):
                raise ContractError(f"map.bases[{player}] does not match map.cells")

    def kind_at(self, x: int, y: int) -> str:
        """Return the cell character at ``(x, y)``."""
        return self.cells[y][x]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "cells": list(self.cells),
            "bases": [list(base) for base in self.bases],
        }

    @classmethod
    def from_dict(cls, data: Any) -> StaticMap:
        data = require_mapping(data, "map")
        cells = require_list(require_key(data, "cells", "map"), "map.cells")
        bases = require_list(require_key(data, "bases", "map"), "map.bases", 2)
        parsed_bases = []
        for player, base in enumerate(bases):
            pair = require_list(base, f"map.bases[{player}]", 2)
            parsed_bases.append(
                (
                    require_int(pair[0], f"map.bases[{player}].x", 0),
                    require_int(pair[1], f"map.bases[{player}].y", 0),
                )
            )
        return cls(
            size=require_int(require_key(data, "size", "map"), "map.size"),
            cells=tuple(cells),
            bases=(parsed_bases[0], parsed_bases[1]),
        )


@dataclass(frozen=True, slots=True)
class MatchState:
    """Complete dynamic simulation state; the input of the state fingerprint."""

    tick: int
    reserves: tuple[int, int]
    move_budgets: tuple[int, int]
    pending_builds: tuple[bool, bool]
    invalid_commands: tuple[int, int]
    next_ship_id: int
    ships: tuple[Ship, ...]
    energy: tuple[EnergyCell, ...]

    def __post_init__(self) -> None:
        ids = [ship.id for ship in self.ships]
        if ids != sorted(set(ids)):
            raise ContractError("state.ships must be unique and in ascending id order")
        if ids and ids[-1] >= self.next_ship_id:
            raise ContractError("state.next_ship_id must be greater than every ship id")
        keys = [(cell.y, cell.x) for cell in self.energy]
        if keys != sorted(set(keys)):
            raise ContractError("state.energy must be unique and in row-major order")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "reserves": list(self.reserves),
            "move_budgets": list(self.move_budgets),
            "pending_builds": list(self.pending_builds),
            "invalid_commands": list(self.invalid_commands),
            "next_ship_id": self.next_ship_id,
            "ships": [ship.to_dict() for ship in self.ships],
            "energy": [cell.to_list() for cell in self.energy],
        }

    @classmethod
    def from_dict(cls, data: Any) -> MatchState:
        data = require_mapping(data, "state")

        def get(key: str) -> Any:
            return require_key(data, key, "state")

        return cls(
            tick=require_int(get("tick"), "state.tick", 0, MAX_TICKS_LIMIT),
            reserves=_int_pair(get("reserves"), "state.reserves"),
            move_budgets=_int_pair(get("move_budgets"), "state.move_budgets"),
            pending_builds=_bool_pair(get("pending_builds"), "state.pending_builds"),
            invalid_commands=_int_pair(
                get("invalid_commands"), "state.invalid_commands"
            ),
            next_ship_id=require_int(get("next_ship_id"), "state.next_ship_id", 0),
            ships=tuple(
                Ship.from_dict(item)
                for item in require_list(get("ships"), "state.ships")
            ),
            energy=tuple(
                EnergyCell.from_list(item)
                for item in require_list(get("energy"), "state.energy")
            ),
        )


@dataclass(frozen=True, slots=True)
class ShipCommand:
    """One action for one ship."""

    ship: int
    action: Action


@dataclass(frozen=True, slots=True)
class PlayerCommands:
    """Commands of one player for one tick.

    ``malformed_entries`` counts move entries that could not be parsed at all;
    each one is counted as an invalid command by the engine.
    """

    moves: tuple[ShipCommand, ...] = ()
    build: bool = False
    malformed_entries: int = 0


@dataclass(frozen=True, slots=True)
class Exclusion:
    """Why and when an agent was excluded (tick 0 = during initialisation)."""

    tick: int
    reason: str

    def __post_init__(self) -> None:
        require_int(self.tick, "exclusion.tick", 0, MAX_TICKS_LIMIT)
        if self.reason not in EXCLUSION_REASONS:
            raise ContractError(f"exclusion.reason is unknown: {self.reason!r}")

    def to_dict(self) -> dict[str, Any]:
        return {"tick": self.tick, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: Any) -> Exclusion:
        data = require_mapping(data, "exclusion")
        return cls(
            tick=require_key(data, "tick", "exclusion"),
            reason=require_key(data, "reason", "exclusion"),
        )


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Final outcome of a match."""

    end_reason: str
    ticks_played: int
    winner: int | None
    decided_by: str
    scores: tuple[int, int]
    ships_remaining: tuple[int, int]
    carried_energy: tuple[int, int]
    invalid_commands: tuple[int, int]
    timeouts: tuple[int, int]
    collisions: int
    exclusions: tuple[Exclusion | None, Exclusion | None] = (None, None)

    def __post_init__(self) -> None:
        if self.end_reason not in END_REASONS:
            raise ContractError(f"result.end_reason is unknown: {self.end_reason!r}")
        if self.decided_by not in DECIDED_BY:
            raise ContractError(f"result.decided_by is unknown: {self.decided_by!r}")
        if self.winner is not None:
            require_int(self.winner, "result.winner", 0, 1)
        if (self.winner is None) != (self.decided_by == "draw"):
            raise ContractError("result.winner must be null exactly for a draw")
        require_int(self.ticks_played, "result.ticks_played", 0, MAX_TICKS_LIMIT)
        require_int(self.collisions, "result.collisions", 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "end_reason": self.end_reason,
            "ticks_played": self.ticks_played,
            "winner": self.winner,
            "decided_by": self.decided_by,
            "scores": list(self.scores),
            "ships_remaining": list(self.ships_remaining),
            "carried_energy": list(self.carried_energy),
            "invalid_commands": list(self.invalid_commands),
            "timeouts": list(self.timeouts),
            "collisions": self.collisions,
            "exclusions": [
                None if item is None else item.to_dict() for item in self.exclusions
            ],
        }

    @classmethod
    def from_dict(cls, data: Any) -> MatchResult:
        data = require_mapping(data, "result")

        def get(key: str) -> Any:
            return require_key(data, key, "result")

        exclusions = require_list(get("exclusions"), "result.exclusions", 2)
        parsed = tuple(
            None if item is None else Exclusion.from_dict(item) for item in exclusions
        )
        winner = get("winner")
        return cls(
            end_reason=get("end_reason"),
            ticks_played=get("ticks_played"),
            winner=winner,
            decided_by=get("decided_by"),
            scores=_int_pair(get("scores"), "result.scores"),
            ships_remaining=_int_pair(get("ships_remaining"), "result.ships_remaining"),
            carried_energy=_int_pair(get("carried_energy"), "result.carried_energy"),
            invalid_commands=_int_pair(
                get("invalid_commands"), "result.invalid_commands"
            ),
            timeouts=_int_pair(get("timeouts"), "result.timeouts"),
            collisions=get("collisions"),
            exclusions=(parsed[0], parsed[1]),
        )
