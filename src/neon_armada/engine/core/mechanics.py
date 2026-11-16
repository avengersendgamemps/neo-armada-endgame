"""Pure game mechanics: deterministic, integer-only state transitions.

Implements sections 5 and 6 of ``contracts/game-models.md``. Nothing here
talks to processes, files, clocks or the GUI; the same inputs always give the
same outputs. Validation (phase 3) is separate from the transition (phases
4-9).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from neon_armada.contracts.models import (
    BUILD_COST,
    CELL_BASES,
    CELL_OBSTACLE,
    INITIAL_BASE_ENERGY,
    MINING_DIVISOR,
    SHIP_CAPACITY,
    Action,
    EnergyCell,
    Exclusion,
    MatchConfig,
    MatchResult,
    MatchState,
    PlayerCommands,
    Ship,
    StaticMap,
)

Event = dict[str, Any]
PLAYERS = (0, 1)


@dataclass(frozen=True, slots=True)
class ValidatedCommands:
    """Result of phase 3 for one player."""

    moves: tuple[tuple[int, Action], ...]  # accepted moves, ascending ship id
    build: bool
    invalid: tuple[Event, ...]  # ``invalid_command`` events, validation order


@dataclass(frozen=True, slots=True)
class TickOutcome:
    """State after one tick, the ordered history events and collision count."""

    state: MatchState
    events: tuple[Event, ...]
    collisions: int


NO_COMMANDS = PlayerCommands()


def create_initial_state(
    config: MatchConfig, static_map: StaticMap, energy: Sequence[EnergyCell]
) -> MatchState:
    """Return the tick-0 state: 1000 energy and one ship on each base."""
    ships = tuple(
        Ship(id=player, owner=player, x=base[0], y=base[1], cargo=0)
        for player, base in enumerate(static_map.bases)
    )
    return MatchState(
        tick=0,
        reserves=(INITIAL_BASE_ENERGY, INITIAL_BASE_ENERGY),
        move_budgets=(config.move_budget, config.move_budget),
        pending_builds=(False, False),
        invalid_commands=(0, 0),
        next_ship_id=len(ships),
        ships=ships,
        energy=tuple(sorted(energy, key=lambda cell: (cell.y, cell.x))),
    )


def _invalid(player: int, reason: str, ship: int | None = None) -> Event:
    event: Event = {"type": "invalid_command", "player": player, "reason": reason}
    if ship is not None:
        event["ship"] = ship
    return event


def validate_commands(
    state: MatchState, static_map: StaticMap, player: int, commands: PlayerCommands
) -> ValidatedCommands:
    """Phase 3: split one player's commands into accepted and ignored ones.

    Uses only the pre-tick state. Ignored commands never consume budget.
    """
    invalid: list[Event] = [
        _invalid(player, "malformed_entry") for _ in range(commands.malformed_entries)
    ]
    own = {ship.id: ship for ship in state.ships if ship.owner == player}
    enemy_base = CELL_BASES[1 - player]
    seen: set[int] = set()
    candidates: dict[int, Action] = {}
    for command in commands.moves:
        ship = own.get(command.ship)
        if ship is None:
            invalid.append(_invalid(player, "unknown_ship", command.ship))
            continue
        if ship.id in seen:
            invalid.append(_invalid(player, "duplicate_ship", ship.id))
            continue
        seen.add(ship.id)
        if command.action is Action.STAY:
            continue
        dx, dy = command.action.delta
        x, y = ship.x + dx, ship.y + dy
        if not static_map.in_bounds(x, y):
            invalid.append(_invalid(player, "out_of_bounds", ship.id))
        elif static_map.kind_at(x, y) == CELL_OBSTACLE:
            invalid.append(_invalid(player, "obstacle", ship.id))
        elif static_map.kind_at(x, y) == enemy_base:
            invalid.append(_invalid(player, "enemy_base", ship.id))
        else:
            candidates[ship.id] = command.action

    budget = state.move_budgets[player]
    moves: list[tuple[int, Action]] = []
    for ship_id in sorted(candidates):
        if len(moves) < budget:
            moves.append((ship_id, candidates[ship_id]))
        else:
            invalid.append(_invalid(player, "no_budget", ship_id))

    build = False
    if commands.build:
        if state.pending_builds[player]:
            invalid.append(_invalid(player, "build_already_pending"))
        elif state.reserves[player] < BUILD_COST:
            invalid.append(_invalid(player, "build_insufficient_energy"))
        else:
            build = True
    return ValidatedCommands(tuple(moves), build, tuple(invalid))


def resolve_tick(
    state: MatchState,
    static_map: StaticMap,
    commands: Sequence[PlayerCommands | None],
    malformed_responses: Sequence[bool] = (False, False),
) -> TickOutcome:
    """Advance the state by one tick (phases 3-9 of the official tick order).

    ``commands[p]`` is ``None`` when player ``p`` sent nothing usable this tick
    (timeout, exclusion, malformed response); its ships then stay in place.
    ``malformed_responses[p]`` records a malformed response, which counts as
    one invalid command.
    """
    events: list[Event] = []
    invalid_counts = list(state.invalid_commands)

    # Phase 3: validation, both players against the same pre-tick state.
    for player in PLAYERS:
        if malformed_responses[player]:
            events.append({"type": "malformed_response", "player": player})
            invalid_counts[player] += 1
    validated = [
        validate_commands(state, static_map, player, commands[player] or NO_COMMANDS)
        for player in PLAYERS
    ]
    for player in PLAYERS:
        events.extend(validated[player].invalid)
        invalid_counts[player] += len(validated[player].invalid)

    ships: dict[int, Ship] = {ship.id: ship for ship in state.ships}
    reserves = list(state.reserves)
    budgets = list(state.move_budgets)
    pending = list(state.pending_builds)
    next_ship_id = state.next_ship_id
    energy = {(cell.x, cell.y): cell.energy for cell in state.energy}

    # Phase 4: construction. Pending builds appear first, then new orders are paid.
    occupied = {(ship.x, ship.y) for ship in ships.values()}
    for player in PLAYERS:
        base = static_map.bases[player]
        if pending[player] and base not in occupied:
            ships[next_ship_id] = Ship(next_ship_id, player, base[0], base[1], 0)
            events.append(
                {
                    "type": "ship_spawned",
                    "player": player,
                    "ship": next_ship_id,
                    "x": base[0],
                    "y": base[1],
                }
            )
            pending[player] = False
            next_ship_id += 1
    for player in PLAYERS:
        if validated[player].build:
            reserves[player] -= BUILD_COST
            pending[player] = True
            events.append(
                {"type": "build_started", "player": player, "cost": BUILD_COST}
            )

    # Phase 5: simultaneous movement from the pre-tick positions.
    accepted = sorted(move for player in PLAYERS for move in validated[player].moves)
    moved: set[int] = set()
    for ship_id, action in accepted:
        ship = ships[ship_id]
        dx, dy = action.delta
        ships[ship_id] = Ship(ship.id, ship.owner, ship.x + dx, ship.y + dy, ship.cargo)
        budgets[ship.owner] -= 1
        moved.add(ship_id)
        events.append(
            {"type": "ship_moved", "ship": ship_id, "x": ship.x + dx, "y": ship.y + dy}
        )

    # Phase 6: collisions. Base cells are exempt (own-base exception).
    by_cell: dict[tuple[int, int], list[int]] = {}
    for ship_id in sorted(ships):
        ship = ships[ship_id]
        by_cell.setdefault((ship.x, ship.y), []).append(ship_id)
    collisions = 0
    for (x, y), ids in sorted(
        by_cell.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        if len(ids) < 2 or static_map.kind_at(x, y) in CELL_BASES:
            continue
        dropped = sum(ships[ship_id].cargo for ship_id in ids)
        for ship_id in ids:
            del ships[ship_id]
        if dropped:
            energy[(x, y)] = energy.get((x, y), 0) + dropped
        collisions += 1
        events.append(
            {"type": "collision", "x": x, "y": y, "ships": ids, "energy_added": dropped}
        )

    # Phase 7: mining by surviving ships that did not change cell.
    for ship_id in sorted(ships):
        ship = ships[ship_id]
        available = energy.get((ship.x, ship.y), 0)
        free = SHIP_CAPACITY - ship.cargo
        if ship_id in moved or available <= 0 or free <= 0:
            continue
        amount = min((available + MINING_DIVISOR - 1) // MINING_DIVISOR, free)
        ships[ship_id] = Ship(ship.id, ship.owner, ship.x, ship.y, ship.cargo + amount)
        if available == amount:
            del energy[(ship.x, ship.y)]
        else:
            energy[(ship.x, ship.y)] = available - amount
        events.append({"type": "mined", "ship": ship_id, "amount": amount})

    # Phase 8: delivery on the own base.
    for ship_id in sorted(ships):
        ship = ships[ship_id]
        if ship.cargo > 0 and (ship.x, ship.y) == static_map.bases[ship.owner]:
            reserves[ship.owner] += ship.cargo
            events.append({"type": "delivered", "ship": ship_id, "amount": ship.cargo})
            ships[ship_id] = Ship(ship.id, ship.owner, ship.x, ship.y, 0)

    # Phase 9: budgets were updated with the moves; assemble the next state.
    new_state = MatchState(
        tick=state.tick + 1,
        reserves=(reserves[0], reserves[1]),
        move_budgets=(budgets[0], budgets[1]),
        pending_builds=(pending[0], pending[1]),
        invalid_commands=(invalid_counts[0], invalid_counts[1]),
        next_ship_id=next_ship_id,
        ships=tuple(ships[ship_id] for ship_id in sorted(ships)),
        energy=tuple(
            EnergyCell(x, y, amount)
            for (x, y), amount in sorted(
                energy.items(), key=lambda item: (item[0][1], item[0][0])
            )
        ),
    )
    return TickOutcome(new_state, tuple(events), collisions)


def can_any_ship_collect(state: MatchState) -> bool:
    """Return True if a ship with free cargo stands on a cell holding energy."""
    cells = {(cell.x, cell.y) for cell in state.energy}
    return any(
        ship.cargo < SHIP_CAPACITY and (ship.x, ship.y) in cells for ship in state.ships
    )


def end_reason(state: MatchState, config: MatchConfig) -> str | None:
    """Return why the match is over after ``state``, or ``None`` to continue."""
    if state.tick >= config.max_ticks:
        return "tick_limit"
    if state.move_budgets == (0, 0) and not can_any_ship_collect(state):
        return "budgets_exhausted"
    return None


def decide_winner(state: MatchState) -> tuple[int | None, str]:
    """Apply score and tie-break rules; return ``(winner, decided_by)``."""
    ship_counts = [0, 0]
    carried = [0, 0]
    for ship in state.ships:
        ship_counts[ship.owner] += 1
        carried[ship.owner] += ship.cargo
    criteria = (
        ("score", state.reserves[0], state.reserves[1]),
        ("ships_remaining", ship_counts[0], ship_counts[1]),
        ("carried_energy", carried[0], carried[1]),
        # Fewer invalid commands is better, hence the swapped operands.
        ("invalid_commands", state.invalid_commands[1], state.invalid_commands[0]),
    )
    for name, first, second in criteria:
        if first != second:
            return (0 if first > second else 1), name
    return None, "draw"


def build_result(
    state: MatchState,
    reason: str,
    timeouts: tuple[int, int] = (0, 0),
    collisions: int = 0,
    exclusions: tuple[Exclusion | None, Exclusion | None] = (None, None),
) -> MatchResult:
    """Assemble the final :class:`MatchResult` for a finished match."""
    winner, decided_by = decide_winner(state)
    ship_counts = [0, 0]
    carried = [0, 0]
    for ship in state.ships:
        ship_counts[ship.owner] += 1
        carried[ship.owner] += ship.cargo
    return MatchResult(
        end_reason=reason,
        ticks_played=state.tick,
        winner=winner,
        decided_by=decided_by,
        scores=state.reserves,
        ships_remaining=(ship_counts[0], ship_counts[1]),
        carried_energy=(carried[0], carried[1]),
        invalid_commands=state.invalid_commands,
        timeouts=timeouts,
        collisions=collisions,
        exclusions=exclusions,
    )
