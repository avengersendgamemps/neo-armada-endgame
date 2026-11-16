"""Tests for seeded symmetric map generation and reachability (L02)."""

from __future__ import annotations

import pytest

from neon_armada.contracts.models import (
    CELL_BASES,
    CELL_DEPOSIT,
    CELL_EMPTY,
    CELL_OBSTACLE,
    ContractError,
    EnergyCell,
    StaticMap,
)
from neon_armada.engine.world.generator import (
    DEFAULT_PARAMS,
    GeneratorParams,
    MapGenerationError,
    build_candidate,
    generate_map,
    is_valid_map,
    reachable_cells,
    rotate,
    unreachable_deposits,
)
from neon_armada.engine.world.rng import SplitMix64, derive_seed

SIZES = (32, 33, 47, 48, 64)
SEEDS = (0, 1, 2, 7, 42, 1234, 2**32, 2**64 - 1)


def test_splitmix64_reference_values() -> None:
    # Published SplitMix64 outputs for seed 0 (e.g. the xoshiro reference code).
    rng = SplitMix64(0)
    assert [rng.next_u64() for _ in range(3)] == [
        0xE220A8397B1DCDAF,
        0x6E789E6AA1B965F4,
        0x06C45D188009454F,
    ]


def test_rng_below_is_bounded_and_deterministic() -> None:
    first = [SplitMix64(99).below(10) for _ in range(1)]
    rng_a, rng_b = SplitMix64(99), SplitMix64(99)
    values = [rng_a.below(10) for _ in range(200)]
    assert values == [rng_b.below(10) for _ in range(200)]
    assert values[0] == first[0]
    assert set(values) <= set(range(10))
    with pytest.raises(ValueError):
        rng_a.below(0)


def test_derived_seeds_are_deterministic_and_distinct() -> None:
    assert derive_seed(42, 0) == 42
    derived = [derive_seed(42, attempt) for attempt in range(1, 20)]
    assert derived == [derive_seed(42, attempt) for attempt in range(1, 20)]
    assert len(set(derived)) == len(derived)
    assert all(0 <= value < 2**64 for value in derived)
    assert derive_seed(42, 1) != derive_seed(43, 1)
    with pytest.raises(ValueError):
        derive_seed(1, -1)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("seed", SEEDS)
def test_generated_map_satisfies_all_official_constraints(seed: int, size: int) -> None:
    generated = generate_map(seed, size)
    static_map, energy = generated.static_map, generated.energy

    # Square map with the requested side.
    assert static_map.size == size
    assert len(static_map.cells) == size
    assert all(len(row) == size for row in static_map.cells)

    # 180-degree rotational symmetry of cell kinds and energy.
    amounts = {(cell.x, cell.y): cell.energy for cell in energy}
    for y in range(size):
        for x in range(size):
            mirror = rotate(size, x, y)
            kind, other = static_map.kind_at(x, y), static_map.kind_at(*mirror)
            if kind in CELL_BASES:
                assert other in CELL_BASES and other != kind
            else:
                assert kind == other
            assert amounts.get((x, y)) == amounts.get(mirror)

    # Exactly one base per player, mirrored, inside the map, with free neighbours.
    base_a, base_b = static_map.bases
    assert rotate(size, *base_a) == base_b
    assert base_a != base_b
    for player, (bx, by) in enumerate(static_map.bases):
        assert static_map.kind_at(bx, by) == CELL_BASES[player]
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dx, dy) != (0, 0):
                    assert static_map.kind_at(bx + dx, by + dy) == CELL_EMPTY

    # Deposits: marker and energy agree, energies within the contract range.
    assert energy
    for y in range(size):
        for x in range(size):
            assert (static_map.kind_at(x, y) == CELL_DEPOSIT) == ((x, y) in amounts)
    assert all(
        DEFAULT_PARAMS.min_deposit_energy
        <= cell.energy
        <= DEFAULT_PARAMS.max_deposit_energy
        for cell in energy
    )
    assert [(c.y, c.x) for c in energy] == sorted((c.y, c.x) for c in energy)

    # Every deposit is reachable from BOTH bases.
    for player in (0, 1):
        reachable = reachable_cells(static_map, player)
        assert all((cell.x, cell.y) in reachable for cell in energy)
    assert unreachable_deposits(static_map, energy) == []


@pytest.mark.parametrize("size", (32, 64))
def test_same_seed_and_size_give_identical_maps(size: int) -> None:
    assert generate_map(2024, size) == generate_map(2024, size)


def test_different_seeds_give_different_maps() -> None:
    maps = {generate_map(seed, 32).static_map.cells for seed in range(20)}
    assert len(maps) == 20


def test_pinned_map_for_generator_version_1() -> None:
    """Regression pin: changing the algorithm requires a new generator version."""
    generated = generate_map(3, 32)
    assert generated.attempt == 0
    assert generated.static_map.bases == ((6, 2), (25, 29))
    assert generated.static_map.cells[0] == "........##..*.....#.*.#....#...#"
    assert generated.static_map.cells[31] == "#...#....#.*.#.....*..##........"


def _first_seed_needing_retry(size: int) -> int:
    for seed in range(2000):
        static_map, energy = build_candidate(size, seed)
        if not is_valid_map(static_map, energy):
            return seed
    raise AssertionError("no seed needing a retry found")


def test_invalid_candidate_is_retried_with_derived_seed() -> None:
    seed = _first_seed_needing_retry(64)
    rejected_map, rejected_energy = build_candidate(64, seed)
    assert unreachable_deposits(rejected_map, rejected_energy)

    generated = generate_map(seed, 64)
    assert generated.attempt >= 1
    assert generated.seed == seed
    assert generated.map_seed == derive_seed(seed, generated.attempt)
    assert build_candidate(64, generated.map_seed) == (
        generated.static_map,
        generated.energy,
    )
    assert is_valid_map(generated.static_map, generated.energy)
    assert generate_map(seed, 64) == generated  # the retry is deterministic


def _map_with(rows: dict[int, str]) -> StaticMap:
    cells = [CELL_EMPTY * 32 for _ in range(32)]
    cells[1] = "." + CELL_BASES[0] + "." * 30
    cells[30] = "." * 30 + CELL_BASES[1] + "."
    for y, row in rows.items():
        cells[y] = row
    return StaticMap(32, tuple(cells), ((1, 1), (30, 30)))


def test_reachability_detects_enclosed_deposit() -> None:
    static_map = _map_with(
        {
            9: "." * 10 + CELL_OBSTACLE + "." * 21,
            10: "." * 9 + CELL_OBSTACLE + CELL_DEPOSIT + CELL_OBSTACLE + "." * 20,
            11: "." * 10 + CELL_OBSTACLE + "." * 21,
        }
    )
    energy = (EnergyCell(10, 10, 100),)
    assert unreachable_deposits(static_map, energy) == [(0, 10, 10), (1, 10, 10)]
    assert not is_valid_map(static_map, energy)


def test_reachability_treats_enemy_base_as_blocked() -> None:
    # A deposit in the corner behind base 1 can only be entered through it.
    static_map = _map_with(
        {
            29: "." * 30 + CELL_OBSTACLE + CELL_OBSTACLE,
            30: "." * 29 + CELL_OBSTACLE + CELL_BASES[1] + CELL_OBSTACLE,
            31: "." * 29 + CELL_OBSTACLE + CELL_DEPOSIT + CELL_OBSTACLE,
        }
    )
    energy = (EnergyCell(30, 31, 100),)
    assert unreachable_deposits(static_map, energy) == [(0, 30, 31)]
    assert (30, 30) not in reachable_cells(static_map, 0)


def test_map_without_deposits_is_invalid() -> None:
    assert not is_valid_map(_map_with({}), ())


@pytest.mark.parametrize("size", (0, 31, 65, 1000))
def test_size_out_of_range_is_rejected(size: int) -> None:
    with pytest.raises(ContractError):
        generate_map(1, size)


@pytest.mark.parametrize("seed", (-1, 2**64, "7", 1.5, True))
def test_seed_out_of_range_is_rejected(seed) -> None:
    with pytest.raises(ContractError):
        generate_map(seed, 32)


def test_impossible_configuration_fails_after_bounded_retries() -> None:
    walls = GeneratorParams(obstacle_percent=90, deposit_percent=10, max_attempts=5)
    with pytest.raises(MapGenerationError, match="5 attempts"):
        generate_map(1, 32, walls)
    no_deposits = GeneratorParams(obstacle_percent=0, deposit_percent=0, max_attempts=3)
    with pytest.raises(MapGenerationError):
        generate_map(1, 32, no_deposits)


def test_generator_params_validation() -> None:
    with pytest.raises(ValueError):
        GeneratorParams(obstacle_percent=60, deposit_percent=50)
    with pytest.raises(ValueError):
        GeneratorParams(min_deposit_energy=10, max_deposit_energy=5)
    with pytest.raises(ValueError):
        GeneratorParams(max_attempts=0)
