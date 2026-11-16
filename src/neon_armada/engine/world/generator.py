"""Seeded, symmetric map generation with reachability validation.

Implements the "Map generator" section (§9) of ``contracts/game-models.md``,
generator version 1. This module knows nothing about ticks, agents or
rendering.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from neon_armada.contracts.models import (
    CELL_BASES,
    CELL_DEPOSIT,
    CELL_EMPTY,
    CELL_OBSTACLE,
    MAX_MAP_SIZE,
    MAX_SEED,
    MIN_MAP_SIZE,
    EnergyCell,
    StaticMap,
    require_int,
)
from neon_armada.engine.world.rng import SplitMix64, derive_seed

_NEIGHBOURS = ((0, -1), (0, 1), (1, 0), (-1, 0))


class MapGenerationError(RuntimeError):
    """No valid map was found within the retry limit."""


@dataclass(frozen=True, slots=True)
class GeneratorParams:
    """Generator constants of version 1 (team decisions, see the contract)."""

    obstacle_percent: int = 12
    deposit_percent: int = 6
    min_deposit_energy: int = 50
    max_deposit_energy: int = 500
    max_attempts: int = 100

    def __post_init__(self) -> None:
        require_int(self.obstacle_percent, "obstacle_percent", 0, 100)
        require_int(self.deposit_percent, "deposit_percent", 0, 100)
        if self.obstacle_percent + self.deposit_percent > 100:
            raise ValueError("obstacle_percent + deposit_percent must be <= 100")
        require_int(self.min_deposit_energy, "min_deposit_energy", 1)
        require_int(
            self.max_deposit_energy, "max_deposit_energy", self.min_deposit_energy
        )
        require_int(self.max_attempts, "max_attempts", 1)


DEFAULT_PARAMS = GeneratorParams()


@dataclass(frozen=True, slots=True)
class GeneratedMap:
    """A validated map together with the seed bookkeeping stored in the history."""

    static_map: StaticMap
    energy: tuple[EnergyCell, ...]
    seed: int
    map_seed: int
    attempt: int


def rotate(size: int, x: int, y: int) -> tuple[int, int]:
    """Return the 180-degree rotation partner of ``(x, y)``."""
    return size - 1 - x, size - 1 - y


def build_candidate(
    size: int, map_seed: int, params: GeneratorParams = DEFAULT_PARAMS
) -> tuple[StaticMap, tuple[EnergyCell, ...]]:
    """Generate one symmetric candidate map without validating reachability."""
    require_int(size, "map_size", MIN_MAP_SIZE, MAX_MAP_SIZE)
    rng = SplitMix64(map_seed)
    base_x = 1 + rng.below(size // 4)
    base_y = 1 + rng.below(size // 4)
    bases = ((base_x, base_y), rotate(size, base_x, base_y))

    grid = [[CELL_EMPTY] * size for _ in range(size)]
    energy: dict[tuple[int, int], int] = {}
    half = (size * size) // 2  # cells whose row-major index is below the partner
    for index in range(half):
        x, y = index % size, index // size
        if any(abs(x - bx) <= 1 and abs(y - by) <= 1 for bx, by in bases):
            continue  # keep the surroundings of both bases free, no PRNG draw
        roll = rng.below(100)
        if roll < params.obstacle_percent:
            kind = CELL_OBSTACLE
        elif roll < params.obstacle_percent + params.deposit_percent:
            kind = CELL_DEPOSIT
            span = params.max_deposit_energy - params.min_deposit_energy + 1
            amount = params.min_deposit_energy + rng.below(span)
            energy[(x, y)] = amount
            energy[rotate(size, x, y)] = amount
        else:
            continue
        mirror_x, mirror_y = rotate(size, x, y)
        grid[y][x] = kind
        grid[mirror_y][mirror_x] = kind

    for player, (x, y) in enumerate(bases):
        grid[y][x] = CELL_BASES[player]
    static_map = StaticMap(
        size=size, cells=tuple("".join(row) for row in grid), bases=bases
    )
    ordered = sorted(energy.items(), key=lambda item: (item[0][1], item[0][0]))
    cells = tuple(EnergyCell(x, y, amount) for (x, y), amount in ordered)
    return static_map, cells


def reachable_cells(static_map: StaticMap, player: int) -> set[tuple[int, int]]:
    """Return the cells ships of ``player`` can reach from their base (BFS).

    Obstacles and the opponent's base cannot be entered.
    """
    blocked = {CELL_OBSTACLE, CELL_BASES[1 - player]}
    start = static_map.bases[player]
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in _NEIGHBOURS:
            nxt = (x + dx, y + dy)
            if (
                nxt not in seen
                and static_map.in_bounds(*nxt)
                and static_map.kind_at(*nxt) not in blocked
            ):
                seen.add(nxt)
                queue.append(nxt)
    return seen


def unreachable_deposits(
    static_map: StaticMap, energy: tuple[EnergyCell, ...]
) -> list[tuple[int, int, int]]:
    """Return ``(player, x, y)`` for every deposit a player cannot reach."""
    missing = []
    for player in (0, 1):
        reachable = reachable_cells(static_map, player)
        missing.extend(
            (player, cell.x, cell.y)
            for cell in energy
            if (cell.x, cell.y) not in reachable
        )
    return missing


def is_valid_map(static_map: StaticMap, energy: tuple[EnergyCell, ...]) -> bool:
    """A map is valid when it has deposits and both bases reach all of them."""
    return bool(energy) and not unreachable_deposits(static_map, energy)


def generate_map(
    seed: int, size: int, params: GeneratorParams = DEFAULT_PARAMS
) -> GeneratedMap:
    """Return the first valid map for ``seed``, retrying with derived seeds.

    Raises :class:`MapGenerationError` after ``params.max_attempts`` invalid
    candidates and ``ContractError`` for an out-of-range seed or size.
    """
    require_int(seed, "seed", 0, MAX_SEED)
    require_int(size, "map_size", MIN_MAP_SIZE, MAX_MAP_SIZE)
    for attempt in range(params.max_attempts):
        map_seed = derive_seed(seed, attempt)
        static_map, energy = build_candidate(size, map_seed, params)
        if is_valid_map(static_map, energy):
            return GeneratedMap(static_map, energy, seed, map_seed, attempt)
    raise MapGenerationError(
        f"no valid map for seed {seed} and size {size} "
        f"after {params.max_attempts} attempts"
    )
