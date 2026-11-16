"""Team agent "Endgame": the Avengers Endgame team's own playing agent.

Strategy (deterministic, integer arithmetic only):

* Fleet economy - builds extra ships early while the investment can still pay
  back and the movement budget can feed another ship.
* Target scoring - every ship picks the deposit with the best expected
  energy per tick of the whole round trip (walk there, mine, walk home),
  instead of simply the nearest one; ships never share a target.
* Safety - ships do not step into cells an enemy ship can reach this tick,
  nor into cells claimed or occupied by friendly ships (the own base is safe).
* Endgame - loaded ships head home in time before the tick limit or the
  movement budget runs out.

Run by the engine as: ``python -u team_agent.py``.
"""

from __future__ import annotations

from neon_agent_kit import (
    BUILD_COST,
    DIRECTIONS,
    SHIP_CAPACITY,
    STAY,
    Commands,
    Game,
    Position,
    Ship,
    TickState,
    apply_action,
    mining_yield,
    run,
)

MAX_SHIPS = 3
RETURN_CARGO = 80
MIN_WORTH = 10
MINING_TICKS = 4  # planning horizon for one mining stop
BUILD_UNTIL_PERCENT = 45  # no new ships after this share of the match
BUDGET_PER_SHIP = 150  # required remaining budget per ship to build another

# Memory between ticks: where each ship stood before its last move.
_previous_position: dict[int, Position] = {}


def _harvest(cell_energy: int, cargo: int, ticks: int) -> int:
    """Energy collected by staying ``ticks`` ticks on a cell."""
    total = 0
    for _ in range(ticks):
        amount = mining_yield(cell_energy, cargo + total)
        if amount <= 0:
            break
        total += amount
        cell_energy -= amount
    return total


def _best_deposit(
    game: Game, state: TickState, ship: Ship, taken: set[Position]
) -> Position | None:
    from_ship = game.distances_from(ship.pos)
    from_base = game.distances_from(game.my_base)
    best_key: tuple[int, int, int] | None = None
    best: Position | None = None
    for (x, y), amount in state.energy.items():
        index = y * game.size + x
        if amount <= MIN_WORTH or from_ship[index] < 0 or (x, y) in taken:
            continue
        gain = _harvest(amount, ship.cargo, MINING_TICKS)
        trip = from_ship[index] + MINING_TICKS + from_base[index]
        key = (-(gain * 1000 // trip), y, x)  # best rate first, then row-major
        if best_key is None or key < best_key:
            best_key, best = key, (x, y)
    return best


def _choose_goal(
    game: Game, state: TickState, ship: Ship, taken: set[Position], fleet: int
) -> Position:
    home = game.my_base
    home_distance = game.distance(ship.pos, home)
    ticks_left = game.max_ticks - state.tick + 1
    budget_share = state.my_budget // max(1, fleet)
    running_out = min(ticks_left, budget_share) <= home_distance + 2
    if ship.cargo >= SHIP_CAPACITY or (ship.cargo > 0 and running_out):
        return home
    here = state.energy.get(ship.pos, 0)
    if mining_yield(here, ship.cargo) >= 3:
        return ship.pos  # the current cell still pays well
    if ship.cargo >= RETURN_CARGO:
        return home
    if state.my_budget <= 0:
        return ship.pos  # cannot move anyway; scrape whatever is here
    target = _best_deposit(game, state, ship, taken)
    if target is not None:
        taken.add(target)
        return target
    if here > 0:
        return ship.pos
    return home if ship.cargo > 0 else ship.pos


def _should_build(game: Game, state: TickState) -> bool:
    fleet = len(state.my_ships)
    return (
        not state.my_pending_build
        and state.my_reserve >= BUILD_COST
        and fleet < MAX_SHIPS
        and state.tick * 100 <= game.max_ticks * BUILD_UNTIL_PERCENT
        and state.my_budget >= BUDGET_PER_SHIP * (fleet + 1)
        and any(amount > MIN_WORTH for amount in state.energy.values())
    )


def decide(game: Game, state: TickState) -> Commands:
    """Return the fleet's commands for this tick."""
    commands = Commands()
    if _should_build(game, state):
        commands.request_build()

    danger: set[Position] = set()
    for enemy in state.enemy_ships:
        danger.add(enemy.pos)
        for _, dx, dy in DIRECTIONS:
            danger.add((enemy.x + dx, enemy.y + dy))
    occupied = {ship.pos for ship in state.my_ships}
    reserved: set[Position] = set()
    taken: set[Position] = set()
    budget = state.my_budget
    fleet = len(state.my_ships)

    # Loaded ships choose first so that they get the shortest way home.
    order = sorted(state.my_ships, key=lambda ship: (-ship.cargo, ship.id))
    for ship in order:
        goal = _choose_goal(game, state, ship, taken, fleet)
        action = STAY
        if goal != ship.pos and budget > 0:
            avoid = (occupied - {ship.pos}) | reserved | danger
            avoid.discard(game.my_base)
            # Do not step straight back: prevents two ships from dancing.
            previous = _previous_position.get(ship.id)
            if previous is not None and previous != goal:
                avoid.add(previous)
            action = game.step_towards(ship.pos, goal, avoid, allow_detour=True)
        if action != STAY:
            budget -= 1
            occupied.discard(ship.pos)  # the cell is free for ships decided later
            _previous_position[ship.id] = ship.pos
        reserved.add(apply_action(ship.pos, action))
        commands.move(ship.id, action)
    return commands


if __name__ == "__main__":
    raise SystemExit(run(decide))
