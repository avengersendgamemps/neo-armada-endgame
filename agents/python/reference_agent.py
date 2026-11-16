"""Reference agent: a deterministic greedy collector.

Used for tests and demonstrations. Each ship walks to the nearest worthwhile
deposit along a shortest path, mines while the cell is rich enough, and
carries the energy home. It never builds ships.

Run by the engine as: ``python -u reference_agent.py``.
"""

from __future__ import annotations

from neon_agent_kit import (
    SHIP_CAPACITY,
    STAY,
    Commands,
    Game,
    Position,
    Ship,
    TickState,
    apply_action,
    run,
)

MIN_WORTH = 20  # cells with this much energy or less are not worth a trip
RETURN_CARGO = 50  # go home instead of to another deposit above this cargo


def _nearest_deposit(
    game: Game, state: TickState, ship: Ship, taken: set[Position]
) -> Position | None:
    distances = game.distances_from(ship.pos)
    best: tuple[int, int, int] | None = None
    for (x, y), amount in state.energy.items():
        distance = distances[y * game.size + x]
        if amount <= MIN_WORTH or distance < 0 or (x, y) in taken:
            continue
        key = (distance, y, x)
        if best is None or key < best:
            best = key
    return None if best is None else (best[2], best[1])


def _choose_goal(
    game: Game, state: TickState, ship: Ship, taken: set[Position]
) -> Position:
    home = game.my_base
    home_distance = game.distance(ship.pos, home)
    ticks_left = game.max_ticks - state.tick + 1
    running_out = min(ticks_left, state.my_budget) <= home_distance + 2
    if ship.cargo >= SHIP_CAPACITY or (ship.cargo > 0 and running_out):
        return home
    here = state.energy.get(ship.pos, 0)
    if here > MIN_WORTH:
        return ship.pos  # keep mining
    if ship.cargo >= RETURN_CARGO:
        return home
    target = _nearest_deposit(game, state, ship, taken)
    if target is not None:
        taken.add(target)
        return target
    if here > 0:
        return ship.pos  # nothing better left: scrape the current cell
    return home if ship.cargo > 0 else ship.pos


def decide(game: Game, state: TickState) -> Commands:
    """Return one command per own ship; never collide with known ships."""
    commands = Commands()
    budget = state.my_budget
    occupied = {ship.pos for ship in state.ships}
    reserved: set[Position] = set()
    taken: set[Position] = set()
    for ship in state.my_ships:
        goal = _choose_goal(game, state, ship, taken)
        action = STAY
        if goal != ship.pos and budget > 0:
            avoid = (occupied - {ship.pos}) | reserved
            avoid.discard(game.my_base)  # own ships may share the base
            action = game.step_towards(ship.pos, goal, avoid)
        if action != STAY:
            budget -= 1
        reserved.add(apply_action(ship.pos, action))
        commands.move(ship.id, action)
    return commands


if __name__ == "__main__":
    raise SystemExit(run(decide))
