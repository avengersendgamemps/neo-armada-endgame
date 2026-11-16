"""Tests for the pure game mechanics (L03). Maps are fixtures, not generated."""

from __future__ import annotations

import dataclasses

import pytest

from neon_armada.contracts.models import (
    Action,
    EnergyCell,
    Exclusion,
    MatchConfig,
    MatchState,
    PlayerCommands,
    Ship,
    ShipCommand,
    StaticMap,
)
from neon_armada.engine.core.mechanics import (
    build_result,
    can_any_ship_collect,
    create_initial_state,
    decide_winner,
    end_reason,
    resolve_tick,
    validate_commands,
)

BASE_A = (3, 4)
BASE_B = (28, 27)
OBSTACLE = (5, 5)


def make_map() -> StaticMap:
    rows = [["."] * 32 for _ in range(32)]
    rows[BASE_A[1]][BASE_A[0]] = "0"
    rows[BASE_B[1]][BASE_B[0]] = "1"
    rows[OBSTACLE[1]][OBSTACLE[0]] = "#"
    rows[26][26] = "#"
    return StaticMap(32, tuple("".join(row) for row in rows), (BASE_A, BASE_B))


MAP = make_map()


def make_state(
    ships: list[Ship],
    energy: dict[tuple[int, int], int] | None = None,
    reserves: tuple[int, int] = (1000, 1000),
    budgets: tuple[int, int] = (1000, 1000),
    pending: tuple[bool, bool] = (False, False),
    tick: int = 0,
    invalid: tuple[int, int] = (0, 0),
) -> MatchState:
    cells = sorted((energy or {}).items(), key=lambda item: (item[0][1], item[0][0]))
    ordered = sorted(ships, key=lambda ship: ship.id)
    return MatchState(
        tick=tick,
        reserves=reserves,
        move_budgets=budgets,
        pending_builds=pending,
        invalid_commands=invalid,
        next_ship_id=max((ship.id for ship in ships), default=-1) + 1,
        ships=tuple(ordered),
        energy=tuple(EnergyCell(x, y, amount) for (x, y), amount in cells),
    )


def cmds(*moves: tuple[int, Action], build: bool = False) -> PlayerCommands:
    return PlayerCommands(
        moves=tuple(ShipCommand(ship, action) for ship, action in moves), build=build
    )


def step(state: MatchState, a: PlayerCommands | None, b: PlayerCommands | None):
    return resolve_tick(state, MAP, (a, b))


def ship_by_id(state: MatchState, ship_id: int) -> Ship:
    return next(ship for ship in state.ships if ship.id == ship_id)


def types(outcome) -> list[str]:
    return [event["type"] for event in outcome.events]


# --- initial state -----------------------------------------------------------


def test_initial_state_has_1000_energy_and_one_ship_each() -> None:
    config = MatchConfig(move_budget=77)
    state = create_initial_state(config, MAP, [EnergyCell(10, 2, 350)])
    assert state.tick == 0
    assert state.reserves == (1000, 1000)
    assert state.move_budgets == (77, 77)
    assert state.ships == (Ship(0, 0, *BASE_A, 0), Ship(1, 1, *BASE_B, 0))
    assert state.next_ship_id == 2
    assert state.pending_builds == (False, False)
    assert state.energy == (EnergyCell(10, 2, 350),)


# --- movement and budget -----------------------------------------------------


@pytest.mark.parametrize(
    "action,expected",
    [
        (Action.NORTH, (10, 9)),
        (Action.SOUTH, (10, 11)),
        (Action.EAST, (11, 10)),
        (Action.WEST, (9, 10)),
    ],
)
def test_move_consumes_one_budget_unit(action: Action, expected) -> None:
    state = make_state([Ship(0, 0, 10, 10)])
    outcome = step(state, cmds((0, action)), None)
    ship = ship_by_id(outcome.state, 0)
    assert (ship.x, ship.y) == expected
    assert outcome.state.move_budgets == (999, 1000)
    assert outcome.events == (
        {"type": "ship_moved", "ship": 0, "x": expected[0], "y": expected[1]},
    )
    assert outcome.state.tick == 1


def test_stay_and_missing_command_are_free() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 0, 12, 12)])
    outcome = step(state, cmds((0, Action.STAY)), None)
    assert outcome.state.ships == state.ships
    assert outcome.state.move_budgets == (1000, 1000)
    assert outcome.state.invalid_commands == (0, 0)
    assert outcome.events == ()


@pytest.mark.parametrize(
    "ship,action,reason",
    [
        (Ship(0, 0, 0, 0), Action.NORTH, "out_of_bounds"),
        (Ship(0, 0, 0, 0), Action.WEST, "out_of_bounds"),
        (Ship(0, 0, 31, 31), Action.SOUTH, "out_of_bounds"),
        (Ship(0, 0, 31, 31), Action.EAST, "out_of_bounds"),
        (Ship(0, 0, 4, 5), Action.EAST, "obstacle"),
        (Ship(0, 0, 28, 26), Action.SOUTH, "enemy_base"),
    ],
)
def test_invalid_moves_are_ignored_counted_and_free(ship, action, reason) -> None:
    state = make_state([ship])
    outcome = step(state, cmds((0, action)), None)
    assert outcome.state.ships == (ship,)
    assert outcome.state.move_budgets == (1000, 1000)
    assert outcome.state.invalid_commands == (1, 0)
    assert outcome.events == (
        {"type": "invalid_command", "player": 0, "reason": reason, "ship": 0},
    )


def test_ship_may_enter_and_leave_own_base() -> None:
    state = make_state([Ship(0, 0, BASE_A[0] - 1, BASE_A[1])])
    outcome = step(state, cmds((0, Action.EAST)), None)
    assert (outcome.state.ships[0].x, outcome.state.ships[0].y) == BASE_A
    assert outcome.state.invalid_commands == (0, 0)


def test_unknown_enemy_and_duplicate_ship_commands_are_invalid() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 1, 20, 20)])
    outcome = step(
        state,
        cmds((1, Action.NORTH), (99, Action.NORTH), (0, Action.EAST), (0, Action.WEST)),
        None,
    )
    assert [(e["reason"], e["ship"]) for e in outcome.events[:3]] == [
        ("unknown_ship", 1),
        ("unknown_ship", 99),
        ("duplicate_ship", 0),
    ]
    assert outcome.state.invalid_commands == (3, 0)
    assert ship_by_id(outcome.state, 0).x == 11  # the first command wins
    assert ship_by_id(outcome.state, 1) == Ship(1, 1, 20, 20)


def test_malformed_entries_and_malformed_response_are_counted() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 1, 20, 20)])
    commands = PlayerCommands(moves=(), build=False, malformed_entries=2)
    outcome = resolve_tick(state, MAP, (commands, None), (False, True))
    assert outcome.state.invalid_commands == (2, 1)
    assert outcome.events == (
        {"type": "malformed_response", "player": 1},
        {"type": "invalid_command", "player": 0, "reason": "malformed_entry"},
        {"type": "invalid_command", "player": 0, "reason": "malformed_entry"},
    )


def test_exhausted_budget_keeps_ships_in_place() -> None:
    state = make_state([Ship(0, 0, 10, 10)], budgets=(0, 5))
    outcome = step(state, cmds((0, Action.EAST)), None)
    assert outcome.state.ships == state.ships
    assert outcome.state.move_budgets == (0, 5)
    assert outcome.events == (
        {"type": "invalid_command", "player": 0, "reason": "no_budget", "ship": 0},
    )


def test_partial_budget_is_spent_in_ascending_ship_id_order() -> None:
    ships = [Ship(4, 0, 10, 10), Ship(2, 0, 12, 12), Ship(7, 0, 14, 14)]
    state = make_state(ships, budgets=(2, 0))
    outcome = step(
        state, cmds((7, Action.EAST), (4, Action.EAST), (2, Action.EAST)), None
    )
    assert ship_by_id(outcome.state, 2).x == 13
    assert ship_by_id(outcome.state, 4).x == 11
    assert ship_by_id(outcome.state, 7).x == 14
    assert outcome.state.move_budgets == (0, 0)
    assert outcome.events[0] == {
        "type": "invalid_command",
        "player": 0,
        "reason": "no_budget",
        "ship": 7,
    }


def test_invalid_moves_do_not_use_budget_needed_by_valid_ones() -> None:
    state = make_state([Ship(0, 0, 0, 0), Ship(1, 0, 10, 10)], budgets=(1, 0))
    outcome = step(state, cmds((0, Action.NORTH), (1, Action.EAST)), None)
    assert ship_by_id(outcome.state, 1).x == 11
    assert outcome.state.move_budgets == (0, 0)


# --- collisions --------------------------------------------------------------


def test_two_enemy_ships_entering_the_same_cell_are_destroyed() -> None:
    state = make_state([Ship(0, 0, 10, 10, 30), Ship(1, 1, 12, 10, 45)])
    outcome = step(state, cmds((0, Action.EAST)), cmds((1, Action.WEST)))
    assert outcome.state.ships == ()
    assert outcome.state.energy == (EnergyCell(11, 10, 75),)
    assert outcome.collisions == 1
    assert outcome.events[-1] == {
        "type": "collision",
        "x": 11,
        "y": 10,
        "ships": [0, 1],
        "energy_added": 75,
    }


def test_collision_is_symmetric_between_players() -> None:
    """Mirrored situation: swapping the owners gives the mirrored outcome."""
    first = make_state([Ship(0, 0, 10, 10, 30), Ship(1, 1, 12, 10, 45)])
    second = make_state([Ship(0, 1, 10, 10, 30), Ship(1, 0, 12, 10, 45)])
    out_first = step(first, cmds((0, Action.EAST)), cmds((1, Action.WEST)))
    out_second = step(second, cmds((1, Action.WEST)), cmds((0, Action.EAST)))
    assert out_first.state.ships == out_second.state.ships == ()
    assert out_first.state.energy == out_second.state.energy


def test_same_player_ships_collide_too() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 0, 12, 10)])
    outcome = step(state, cmds((0, Action.EAST), (1, Action.WEST)), None)
    assert outcome.state.ships == ()
    assert outcome.state.energy == ()  # nothing carried, nothing dropped


def test_moving_into_a_stationary_ship_destroys_both() -> None:
    state = make_state([Ship(0, 0, 10, 10, 10), Ship(1, 1, 11, 10, 5)])
    outcome = step(state, cmds((0, Action.EAST)), cmds((1, Action.STAY)))
    assert outcome.state.ships == ()
    assert outcome.state.energy == (EnergyCell(11, 10, 15),)


def test_three_ships_in_one_cell_are_all_destroyed() -> None:
    ships = [Ship(0, 0, 10, 10, 1), Ship(1, 1, 12, 10, 2), Ship(2, 1, 11, 9, 3)]
    state = make_state(ships)
    outcome = step(
        state, cmds((0, Action.EAST)), cmds((1, Action.WEST), (2, Action.SOUTH))
    )
    assert outcome.state.ships == ()
    assert outcome.state.energy == (EnergyCell(11, 10, 6),)
    assert outcome.collisions == 1


def test_swapping_cells_is_not_a_collision() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 1, 11, 10)])
    outcome = step(state, cmds((0, Action.EAST)), cmds((1, Action.WEST)))
    assert outcome.state.ships == (Ship(0, 0, 11, 10), Ship(1, 1, 10, 10))
    assert outcome.collisions == 0
    assert "collision" not in types(outcome)


def test_following_ship_does_not_collide() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 0, 11, 10)])
    outcome = step(state, cmds((0, Action.EAST), (1, Action.EAST)), None)
    assert outcome.state.ships == (Ship(0, 0, 11, 10), Ship(1, 0, 12, 10))


def test_cargo_is_added_to_existing_deposit_energy() -> None:
    state = make_state(
        [Ship(0, 0, 10, 10, 40), Ship(1, 1, 12, 10, 0)], energy={(11, 10): 100}
    )
    outcome = step(state, cmds((0, Action.EAST)), cmds((1, Action.WEST)))
    assert outcome.state.energy == (EnergyCell(11, 10, 140),)


def test_own_base_is_exempt_from_collisions() -> None:
    ships = [Ship(0, 0, *BASE_A, 0), Ship(1, 0, BASE_A[0] + 1, BASE_A[1], 60)]
    state = make_state(ships)
    outcome = step(state, cmds((1, Action.WEST)), None)
    assert len(outcome.state.ships) == 2
    assert outcome.collisions == 0
    assert outcome.state.reserves == (1060, 1000)
    assert ship_by_id(outcome.state, 1).cargo == 0


def test_simultaneous_collisions_are_reported_in_row_major_order() -> None:
    ships = [
        Ship(0, 0, 20, 20),
        Ship(1, 1, 22, 20),
        Ship(2, 0, 10, 10),
        Ship(3, 1, 12, 10),
    ]
    outcome = step(
        make_state(ships),
        cmds((0, Action.EAST), (2, Action.EAST)),
        cmds((1, Action.WEST), (3, Action.WEST)),
    )
    collisions = [e for e in outcome.events if e["type"] == "collision"]
    assert [(e["x"], e["y"]) for e in collisions] == [(11, 10), (21, 20)]
    assert outcome.collisions == 2


# --- mining ------------------------------------------------------------------


@pytest.mark.parametrize(
    "cell_energy,cargo,expected",
    [
        (350, 0, 35),
        (351, 0, 36),  # ceil(351 / 10)
        (9, 0, 1),
        (1, 0, 1),
        (10, 0, 1),
        (11, 0, 2),
        (500, 70, 30),  # limited by free cargo
        (500, 100, 0),  # full cargo
    ],
)
def test_stationary_ship_mines_a_tenth_rounded_up(cell_energy, cargo, expected) -> None:
    state = make_state([Ship(0, 0, 10, 10, cargo)], energy={(10, 10): cell_energy})
    outcome = step(state, None, None)
    assert outcome.state.ships[0].cargo == cargo + expected
    remaining = cell_energy - expected
    assert outcome.state.energy == (
        (EnergyCell(10, 10, remaining),) if remaining else ()
    )
    if expected:
        assert outcome.events == ({"type": "mined", "ship": 0, "amount": expected},)
    else:
        assert outcome.events == ()


def test_ship_that_moves_onto_a_deposit_does_not_mine_that_tick() -> None:
    state = make_state([Ship(0, 0, 9, 10)], energy={(10, 10): 200})
    moved = step(state, cmds((0, Action.EAST)), None)
    assert moved.state.ships[0].cargo == 0
    assert moved.state.energy == (EnergyCell(10, 10, 200),)
    stayed = step(moved.state, cmds((0, Action.STAY)), None)
    assert stayed.state.ships[0].cargo == 20


def test_ship_whose_move_was_ignored_still_mines() -> None:
    state = make_state([Ship(0, 0, 4, 5)], energy={(4, 5): 100})
    outcome = step(state, cmds((0, Action.EAST)), None)  # obstacle
    assert outcome.state.ships[0].cargo == 10
    assert types(outcome) == ["invalid_command", "mined"]


def test_depleted_cell_disappears_from_energy() -> None:
    state = make_state([Ship(0, 0, 10, 10)], energy={(10, 10): 3})
    for expected in (1, 1, 1):
        outcome = step(state, None, None)
        assert outcome.events == ({"type": "mined", "ship": 0, "amount": expected},)
        state = outcome.state
    assert state.energy == ()
    assert state.ships[0].cargo == 3
    assert step(state, None, None).events == ()


def test_cargo_never_exceeds_capacity_over_many_ticks() -> None:
    state = make_state([Ship(0, 0, 10, 10)], energy={(10, 10): 500})
    for _ in range(20):
        state = step(state, None, None).state
        assert 0 <= state.ships[0].cargo <= 100
    assert state.ships[0].cargo == 100
    assert state.energy == (EnergyCell(10, 10, 400),)


def test_collision_cargo_can_be_mined_from_an_empty_cell() -> None:
    state = make_state([Ship(0, 0, 10, 10, 50), Ship(1, 1, 12, 10, 50)])
    after = step(state, cmds((0, Action.EAST)), cmds((1, Action.WEST))).state
    with_miner = dataclasses.replace(
        after, ships=(Ship(5, 0, 11, 10, 0),), next_ship_id=6
    )
    assert step(with_miner, None, None).state.ships[0].cargo == 10


# --- delivery ----------------------------------------------------------------


def test_ship_delivers_whole_cargo_when_reaching_own_base() -> None:
    state = make_state([Ship(0, 0, BASE_A[0], BASE_A[1] + 1, 87)])
    outcome = step(state, cmds((0, Action.NORTH)), None)
    assert outcome.state.reserves == (1087, 1000)
    assert outcome.state.ships[0].cargo == 0
    assert outcome.events[-1] == {"type": "delivered", "ship": 0, "amount": 87}


def test_tick_phase_order_move_then_collide_then_mine_then_deliver() -> None:
    ships = [
        Ship(0, 0, BASE_A[0] + 1, BASE_A[1], 40),  # moves home and delivers
        Ship(1, 1, 20, 20, 0),  # stays and mines
        Ship(2, 0, 10, 10, 5),  # collides with 3
        Ship(3, 1, 12, 10, 5),
    ]
    state = make_state(ships, energy={(20, 20): 100}, pending=(False, True))
    outcome = step(
        state,
        cmds((0, Action.WEST), (2, Action.EAST), (0, Action.EAST), build=True),
        cmds((3, Action.WEST)),
    )
    assert types(outcome) == [
        "invalid_command",  # phase 3 (duplicate command for ship 0)
        "ship_spawned",  # phase 4 (player 1 pending build)
        "build_started",  # phase 4 (player 0 new order)
        "ship_moved",  # phase 5
        "ship_moved",
        "ship_moved",
        "collision",  # phase 6
        "mined",  # phase 7
        "delivered",  # phase 8
    ]


# --- construction ------------------------------------------------------------


def test_build_costs_500_and_ship_appears_on_the_next_tick() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 1, 20, 20)])
    ordered = step(state, cmds(build=True), None)
    assert ordered.state.reserves == (500, 1000)
    assert ordered.state.pending_builds == (True, False)
    assert len(ordered.state.ships) == 2  # not yet
    assert ordered.events == ({"type": "build_started", "player": 0, "cost": 500},)

    spawned = step(ordered.state, None, None)
    assert spawned.state.pending_builds == (False, False)
    assert spawned.state.ships[-1] == Ship(2, 0, *BASE_A, 0)
    assert spawned.state.next_ship_id == 3
    assert spawned.events == (
        {"type": "ship_spawned", "player": 0, "ship": 2, "x": 3, "y": 4},
    )


def test_build_with_insufficient_energy_is_invalid() -> None:
    state = make_state([Ship(0, 0, 10, 10)], reserves=(499, 1000))
    outcome = step(state, cmds(build=True), None)
    assert outcome.state.reserves == (499, 1000)
    assert outcome.state.pending_builds == (False, False)
    assert outcome.events == (
        {"type": "invalid_command", "player": 0, "reason": "build_insufficient_energy"},
    )


def test_build_with_exactly_500_is_allowed() -> None:
    state = make_state([Ship(0, 0, 10, 10)], reserves=(500, 1000))
    assert step(state, cmds(build=True), None).state.reserves == (0, 1000)


def test_second_build_while_pending_is_invalid() -> None:
    state = make_state([Ship(0, 0, 10, 10)], pending=(True, False))
    outcome = step(state, cmds(build=True), None)
    assert outcome.state.reserves == (1000, 1000)
    assert outcome.events[0]["reason"] == "build_already_pending"
    assert outcome.state.invalid_commands == (1, 0)


def test_spawn_waits_while_the_base_is_occupied() -> None:
    state = make_state([Ship(0, 0, *BASE_A)], pending=(True, False))
    blocked = step(state, None, None)
    assert blocked.state.pending_builds == (True, False)
    assert len(blocked.state.ships) == 1

    # The ship leaves; the base was still occupied at construction time.
    leaving = step(blocked.state, cmds((0, Action.EAST)), None)
    assert leaving.state.pending_builds == (True, False)
    assert len(leaving.state.ships) == 1

    free = step(leaving.state, None, None)
    assert free.state.pending_builds == (False, False)
    assert len(free.state.ships) == 2


def test_new_ship_cannot_be_commanded_in_its_spawn_tick() -> None:
    state = make_state([Ship(0, 0, 10, 10)], pending=(True, False))
    outcome = step(state, cmds((1, Action.EAST)), None)
    assert outcome.events[0] == {
        "type": "invalid_command",
        "player": 0,
        "reason": "unknown_ship",
        "ship": 1,
    }
    assert ship_by_id(outcome.state, 1) == Ship(1, 0, *BASE_A, 0)


def test_both_players_spawning_get_ids_in_player_order() -> None:
    state = make_state([Ship(0, 0, 10, 10), Ship(1, 1, 20, 20)], pending=(True, True))
    outcome = step(state, None, None)
    assert ship_by_id(outcome.state, 2).owner == 0
    assert ship_by_id(outcome.state, 3).owner == 1


# --- validation is separate and pure -----------------------------------------


def test_validate_commands_does_not_change_state() -> None:
    state = make_state([Ship(0, 0, 10, 10)])
    validated = validate_commands(state, MAP, 0, cmds((0, Action.EAST), build=True))
    assert validated.moves == ((0, Action.EAST),)
    assert validated.build is True
    assert validated.invalid == ()
    assert state == make_state([Ship(0, 0, 10, 10)])


def test_resolve_tick_is_deterministic_and_does_not_mutate_input() -> None:
    state = make_state(
        [Ship(0, 0, 10, 10, 5), Ship(1, 1, 12, 10, 7)], energy={(10, 10): 90}
    )
    commands = (cmds((0, Action.STAY), build=True), cmds((1, Action.WEST)))
    snapshot = state.to_dict()
    first = resolve_tick(state, MAP, commands)
    second = resolve_tick(state, MAP, commands)
    assert first == second
    assert state.to_dict() == snapshot


def test_state_uses_integers_only() -> None:
    state = make_state([Ship(0, 0, 10, 10)], energy={(10, 10): 333})
    for _ in range(15):
        state = step(state, None, None).state

    def walk(value) -> None:
        assert not isinstance(value, float)
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(state.to_dict())


# --- end of match and scoring ------------------------------------------------


def test_match_ends_at_the_tick_limit() -> None:
    config = MatchConfig(max_ticks=500)
    ships = [Ship(0, 0, 10, 10)]
    assert end_reason(make_state(ships, tick=499), config) is None
    assert end_reason(make_state(ships, tick=500), config) == "tick_limit"


def test_early_end_needs_both_budgets_exhausted_and_no_collecting_ship() -> None:
    config = MatchConfig()
    ships = [Ship(0, 0, 10, 10, 0), Ship(1, 1, 20, 20, 100)]
    energy = {(10, 10): 50, (20, 20): 50}
    # One budget left: continue.
    assert end_reason(make_state(ships, energy, budgets=(0, 1), tick=5), config) is None
    # Both exhausted but ship 0 can still mine: continue.
    still = make_state(ships, energy, budgets=(0, 0), tick=5)
    assert can_any_ship_collect(still)
    assert end_reason(still, config) is None
    # Both exhausted, ship 0's cell is empty, ship 1 is full: end.
    done = make_state(ships, {(20, 20): 50}, budgets=(0, 0), tick=5)
    assert not can_any_ship_collect(done)
    assert end_reason(done, config) == "budgets_exhausted"


def test_zero_budget_match_mines_out_then_ends_early() -> None:
    config = MatchConfig(move_budget=0)
    state = make_state([Ship(0, 0, 10, 10)], energy={(10, 10): 12}, budgets=(0, 0))
    ticks = 0
    while end_reason(state, config) is None:
        state = step(state, None, None).state
        ticks += 1
    assert end_reason(state, config) == "budgets_exhausted"
    assert state.energy == ()
    assert ticks < 500


@pytest.mark.parametrize(
    "state_kwargs,ships,expected",
    [
        ({"reserves": (900, 800)}, [], (0, "score")),
        ({"reserves": (800, 900)}, [], (1, "score")),
        (
            {},
            [Ship(0, 1, 1, 1), Ship(1, 1, 2, 2), Ship(2, 0, 3, 3)],
            (1, "ships_remaining"),
        ),
        ({}, [Ship(0, 0, 1, 1, 30), Ship(1, 1, 2, 2, 10)], (0, "carried_energy")),
        (
            {"invalid": (4, 1)},
            [Ship(0, 0, 1, 1), Ship(1, 1, 2, 2)],
            (1, "invalid_commands"),
        ),
        ({}, [Ship(0, 0, 1, 1), Ship(1, 1, 2, 2)], (None, "draw")),
    ],
)
def test_score_and_tie_break_order(state_kwargs, ships, expected) -> None:
    assert decide_winner(make_state(ships, **state_kwargs)) == expected


def test_build_result_summarises_the_final_state() -> None:
    state = make_state(
        [Ship(0, 0, 1, 1, 30), Ship(1, 1, 2, 2, 10), Ship(2, 1, 5, 6, 0)],
        reserves=(1500, 1500),
        tick=500,
        invalid=(2, 0),
    )
    result = build_result(
        state, "tick_limit", (1, 3), 4, (None, Exclusion(17, "timeout"))
    )
    assert result.to_dict() == {
        "end_reason": "tick_limit",
        "ticks_played": 500,
        "winner": 1,
        "decided_by": "ships_remaining",
        "scores": [1500, 1500],
        "ships_remaining": [1, 2],
        "carried_energy": [30, 10],
        "invalid_commands": [2, 0],
        "timeouts": [1, 3],
        "collisions": 4,
        "exclusions": [None, {"tick": 17, "reason": "timeout"}],
    }
