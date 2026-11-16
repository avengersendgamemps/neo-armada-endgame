"""Presentation adapter: history data to render-ready frames.

This module is the only place where the client interprets a match history. It
depends on the shared contracts (reader and event-based reconstruction) and on
nothing else: no Qt, no engine code, no game rules. Widgets consume the
immutable :class:`FrameView` objects produced here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from neon_armada.contracts.models import MatchState
from neon_armada.contracts.replay import History, load_history, reconstruct_states


@dataclass(frozen=True, slots=True)
class ShipView:
    id: int
    owner: int
    x: int
    y: int
    cargo: int
    mining: bool


@dataclass(frozen=True, slots=True)
class PlayerView:
    name: str
    reserve: int
    move_budget: int
    ships: int
    carried: int
    invalid_commands: int
    pending_build: bool
    excluded: str | None  # e.g. "timeout at tick 3", once it has happened


@dataclass(frozen=True, slots=True)
class FrameView:
    """Everything a widget needs to draw one tick."""

    tick: int
    last_tick: int
    size: int
    cells: tuple[str, ...]
    bases: tuple[tuple[int, int], tuple[int, int]]
    energy: tuple[tuple[int, int, int], ...]
    max_energy: int
    ships: tuple[ShipView, ...]
    players: tuple[PlayerView, PlayerView]
    collisions: tuple[tuple[int, int], ...]
    event_summary: tuple[str, ...]
    result_text: str | None  # set on the last frame only


def _describe(event: dict, names: tuple[str, str]) -> str | None:
    kind = event["type"]
    if kind == "collision":
        return f"Collision at ({event['x']}, {event['y']}): ships {event['ships']}"
    if kind == "ship_spawned":
        return f"{names[event['player']]} launched ship {event['ship']}"
    if kind == "build_started":
        return f"{names[event['player']]} ordered a ship ({event['cost']})"
    if kind == "delivered":
        return f"Ship {event['ship']} delivered {event['amount']}"
    if kind == "timeout":
        return f"{names[event['player']]} timed out ({event['consecutive']} in a row)"
    if kind == "agent_excluded":
        return f"{names[event['player']]} excluded: {event['reason']}"
    if kind == "malformed_response":
        return f"{names[event['player']]} sent a malformed response"
    if kind == "invalid_command":
        return f"{names[event['player']]} invalid command: {event['reason']}"
    return None  # moves and mining are visible on the map


class MatchPresentation:
    """A loaded match: every tick reconstructed and ready to be framed."""

    def __init__(self, history: History) -> None:
        self.history = history
        # Raises HistoryError if the events cannot be applied.
        self._states: list[MatchState] = reconstruct_states(history)
        self._max_energy = max(
            (cell.energy for cell in history.initial_state.energy), default=1
        )

    @classmethod
    def from_file(cls, path: str | Path) -> MatchPresentation:
        """Load a history file; raises ``HistoryError`` when it is unusable."""
        return cls(load_history(path))

    @property
    def last_tick(self) -> int:
        return len(self._states) - 1

    @property
    def title(self) -> str:
        names = self.history.agent_names
        return f"{names[0]} vs {names[1]} - seed {self.history.seed}"

    def clamp(self, tick: int) -> int:
        return max(0, min(self.last_tick, tick))

    def frame(self, tick: int) -> FrameView:
        """Return the frame after ``tick`` ticks (0 = initial state)."""
        if not 0 <= tick <= self.last_tick:
            raise IndexError(f"tick {tick} is outside 0..{self.last_tick}")
        history = self.history
        state = self._states[tick]
        if tick == 0:
            events = history.setup_events
        else:
            events = history.ticks[tick - 1].events
        mining = {event["ship"] for event in events if event["type"] == "mined"}
        players = []
        for player in (0, 1):
            own = [ship for ship in state.ships if ship.owner == player]
            exclusion = history.result.exclusions[player]
            excluded = None
            if exclusion is not None and exclusion.tick <= tick:
                excluded = f"{exclusion.reason} at tick {exclusion.tick}"
            players.append(
                PlayerView(
                    name=history.agent_names[player],
                    reserve=state.reserves[player],
                    move_budget=state.move_budgets[player],
                    ships=len(own),
                    carried=sum(ship.cargo for ship in own),
                    invalid_commands=state.invalid_commands[player],
                    pending_build=state.pending_builds[player],
                    excluded=excluded,
                )
            )
        summary = tuple(
            text
            for text in (_describe(event, history.agent_names) for event in events)
            if text is not None
        )
        return FrameView(
            tick=tick,
            last_tick=self.last_tick,
            size=history.static_map.size,
            cells=history.static_map.cells,
            bases=history.static_map.bases,
            energy=tuple((cell.x, cell.y, cell.energy) for cell in state.energy),
            max_energy=self._max_energy,
            ships=tuple(
                ShipView(s.id, s.owner, s.x, s.y, s.cargo, s.id in mining)
                for s in state.ships
            ),
            players=(players[0], players[1]),
            collisions=tuple(
                (event["x"], event["y"])
                for event in events
                if event["type"] == "collision"
            ),
            event_summary=summary,
            result_text=self._result_text() if tick == self.last_tick else None,
        )

    def _result_text(self) -> str:
        result = self.history.result
        reason = result.end_reason.replace("_", " ")
        if result.winner is None:
            return f"Draw ({reason})"
        name = self.history.agent_names[result.winner]
        decided = result.decided_by.replace("_", " ")
        return f"Winner: {name} - decided by {decided} ({reason})"
