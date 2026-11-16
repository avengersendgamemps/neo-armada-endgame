"""Neon Armada agent starter kit for Python (protocol version 1).

A self-contained helper module for writing agents. It depends only on the
Python standard library and never imports the engine: an agent is an
independent program that talks to the engine through stdin/stdout as described
in ``contracts/agent-protocol.md``.

Minimal agent::

    from neon_agent_kit import Commands, run

    def decide(game, state):
        commands = Commands()
        for ship in state.my_ships:
            commands.move(ship.id, "STAY")
        return commands

    if __name__ == "__main__":
        raise SystemExit(run(decide))

Rules of the road: stdout is reserved for protocol messages (the kit writes
them); use :func:`log` for diagnostics, which go to stderr.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, BinaryIO

PROTOCOL_VERSION = 1
SHIP_CAPACITY = 100
BUILD_COST = 500
MINING_DIVISOR = 10

NORTH, SOUTH, EAST, WEST, STAY = "N", "S", "E", "W", "STAY"
DIRECTIONS = ((NORTH, 0, -1), (SOUTH, 0, 1), (EAST, 1, 0), (WEST, -1, 0))
_DELTAS = {name: (dx, dy) for name, dx, dy in DIRECTIONS} | {STAY: (0, 0)}
_DISTANCE_CACHE_LIMIT = 512

Position = tuple[int, int]


def log(*parts: object) -> None:
    """Write a diagnostic line to stderr (never to stdout)."""
    print(*parts, file=sys.stderr, flush=True)


def apply_action(position: Position, action: str) -> Position:
    """Return the cell reached from ``position`` by ``action``."""
    dx, dy = _DELTAS[action]
    return position[0] + dx, position[1] + dy


def mining_yield(cell_energy: int, cargo: int = 0) -> int:
    """Energy a stationary ship collects in one tick: ceil(e / 10), cargo-capped."""
    if cell_energy <= 0:
        return 0
    return min(
        (cell_energy + MINING_DIVISOR - 1) // MINING_DIVISOR, SHIP_CAPACITY - cargo
    )


@dataclass(frozen=True)
class Ship:
    """A ship as reported by the engine."""

    id: int
    owner: int
    x: int
    y: int
    cargo: int

    @property
    def pos(self) -> Position:
        return self.x, self.y


class Game:
    """Static match data from the ``init`` message plus path-finding helpers."""

    def __init__(self, message: dict[str, Any]) -> None:
        self.player_id: int = message["player_id"]
        self.config: dict[str, int] = dict(message["config"])
        self.max_ticks: int = self.config["max_ticks"]
        game_map = message["map"]
        self.size: int = game_map["size"]
        self.cells: list[str] = list(game_map["cells"])
        self.bases: list[Position] = [tuple(base) for base in game_map["bases"]]
        self.my_base: Position = self.bases[self.player_id]
        self.enemy_base: Position = self.bases[1 - self.player_id]
        enemy_char = str(1 - self.player_id)
        self._passable = [
            char != "#" and char != enemy_char for row in self.cells for char in row
        ]
        self._distance_cache: dict[Position, list[int]] = {}

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def passable(self, x: int, y: int) -> bool:
        """True if my ships may enter the cell (no obstacle, not the enemy base)."""
        return self.in_bounds(x, y) and self._passable[y * self.size + x]

    def distances_from(self, origin: Position) -> list[int]:
        """Breadth-first distances from ``origin`` to every cell.

        The result is a flat list indexed by ``y * size + x``; unreachable
        cells hold ``-1``. Results are cached.
        """
        cached = self._distance_cache.get(origin)
        if cached is not None:
            return cached
        size = self.size
        passable = self._passable
        distances = [-1] * (size * size)
        start = origin[1] * size + origin[0]
        distances[start] = 0
        queue = deque([start])
        while queue:
            index = queue.popleft()
            step = distances[index] + 1
            x = index % size
            if index >= size:
                self._visit(index - size, step, distances, passable, queue)
            if index + size < size * size:
                self._visit(index + size, step, distances, passable, queue)
            if x + 1 < size:
                self._visit(index + 1, step, distances, passable, queue)
            if x > 0:
                self._visit(index - 1, step, distances, passable, queue)
        if len(self._distance_cache) >= _DISTANCE_CACHE_LIMIT:
            self._distance_cache.clear()
        self._distance_cache[origin] = distances
        return distances

    @staticmethod
    def _visit(
        index: int, step: int, distances: list[int], passable: list[bool], queue: deque
    ) -> None:
        if distances[index] < 0 and passable[index]:
            distances[index] = step
            queue.append(index)

    def distance(self, start: Position, goal: Position) -> int:
        """Shortest path length between two cells, or ``-1`` if unreachable."""
        return self.distances_from(goal)[start[1] * self.size + start[0]]

    def step_towards(
        self,
        start: Position,
        goal: Position,
        avoid: Iterable[Position] = (),
        allow_detour: bool = False,
    ) -> str:
        """Return the action that brings ``start`` one step closer to ``goal``.

        Cells in ``avoid`` are never entered. Returns ``STAY`` when already at
        the goal. When every strictly closer neighbour is blocked the result
        is ``STAY``, unless ``allow_detour`` is set: then the free neighbour
        nearest to the goal is chosen so that ships can walk around each other.
        """
        if start == goal:
            return STAY
        distances = self.distances_from(goal)
        blocked = set(avoid)
        current = distances[start[1] * self.size + start[0]]
        if current < 0:
            return STAY
        best_action = STAY
        best = -1
        for name, dx, dy in DIRECTIONS:
            x, y = start[0] + dx, start[1] + dy
            if not self.in_bounds(x, y) or (x, y) in blocked:
                continue
            candidate = distances[y * self.size + x]
            if candidate >= 0 and (best < 0 or candidate < best):
                best_action, best = name, candidate
        if best < 0 or (best >= current and not allow_detour):
            return STAY
        return best_action


class TickState:
    """Dynamic state from one ``tick`` message."""

    def __init__(self, message: dict[str, Any], player_id: int) -> None:
        self.tick: int = message["tick"]
        self.reserves: list[int] = list(message["reserves"])
        self.move_budgets: list[int] = list(message["move_budgets"])
        self.pending_builds: list[bool] = list(message["pending_builds"])
        self.ships: list[Ship] = [
            Ship(s["id"], s["owner"], s["x"], s["y"], s["cargo"])
            for s in message["ships"]
        ]
        self.energy: dict[Position, int] = {
            (x, y): amount for x, y, amount in message["energy"]
        }
        self.my_ships = [ship for ship in self.ships if ship.owner == player_id]
        self.enemy_ships = [ship for ship in self.ships if ship.owner != player_id]
        self.my_reserve: int = self.reserves[player_id]
        self.my_budget: int = self.move_budgets[player_id]
        self.my_pending_build: bool = self.pending_builds[player_id]


class Commands:
    """Commands of one tick: at most one action per ship and one build request."""

    def __init__(self) -> None:
        self.moves: dict[int, str] = {}
        self.build = False

    def move(self, ship_id: int, action: str) -> None:
        if action not in _DELTAS:
            raise ValueError(f"unknown action: {action!r}")
        self.moves[ship_id] = action

    def request_build(self) -> None:
        self.build = True

    def to_message(self, tick: int) -> dict[str, Any]:
        return {
            "type": "commands",
            "tick": tick,
            "moves": [
                {"ship": ship_id, "action": action}
                for ship_id, action in sorted(self.moves.items())
            ],
            "build": self.build,
        }


def _write(stream: BinaryIO, message: dict[str, Any]) -> None:
    stream.write(json.dumps(message, separators=(",", ":")).encode("ascii") + b"\n")
    stream.flush()


def run(
    decide: Callable[[Game, TickState], Commands | None],
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
) -> int:
    """Run the protocol loop until ``end`` or end of input; return an exit code.

    ``decide(game, state)`` is called once per tick. If it raises, the error is
    logged to stderr and an empty command list is sent so the tick is not lost
    to a timeout.
    """
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    game: Game | None = None
    for raw in iter(stdin.readline, b""):
        if not raw.strip():
            continue
        try:
            message = json.loads(raw)
            kind = message["type"]
        except (ValueError, KeyError, TypeError):
            log("neon_agent_kit: malformed message from engine")
            return 1
        if kind == "init":
            if message.get("protocol_version") != PROTOCOL_VERSION:
                log("neon_agent_kit: unsupported protocol version")
                return 1
            game = Game(message)
            _write(stdout, {"type": "ready", "protocol_version": PROTOCOL_VERSION})
        elif kind == "tick":
            if game is None:
                log("neon_agent_kit: tick received before init")
                return 1
            state = TickState(message, game.player_id)
            try:
                commands = decide(game, state) or Commands()
            except Exception:  # keep playing after a strategy bug
                log(traceback.format_exc())
                commands = Commands()
            _write(stdout, commands.to_message(state.tick))
        elif kind == "end":
            return 0
        else:
            log(f"neon_agent_kit: unknown message type {kind!r}")
            return 1
    return 0
