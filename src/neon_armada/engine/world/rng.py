"""Deterministic integer PRNG fixed by the map-generator contract.

SplitMix64 is used because it is tiny, integer-only and trivially identical on
every platform. See ``contracts/game-models.md`` §9.
"""

from __future__ import annotations

MASK64 = 2**64 - 1
_GAMMA = 0x9E3779B97F4A7C15


class SplitMix64:
    """SplitMix64 generator over unsigned 64-bit integers."""

    def __init__(self, seed: int) -> None:
        self._state = seed & MASK64

    def next_u64(self) -> int:
        """Return the next 64-bit value."""
        self._state = (self._state + _GAMMA) & MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def below(self, bound: int) -> int:
        """Return a value in ``[0, bound)`` as ``next_u64() % bound``."""
        if bound <= 0:
            raise ValueError("bound must be positive")
        return self.next_u64() % bound


def mix64(value: int) -> int:
    """Return the first SplitMix64 output for ``value`` used as a seed."""
    return SplitMix64(value).next_u64()


def derive_seed(seed: int, attempt: int) -> int:
    """Return the map seed of retry ``attempt`` (``0`` is the seed itself)."""
    if attempt < 0:
        raise ValueError("attempt must not be negative")
    if attempt == 0:
        return seed & MASK64
    return mix64((seed & MASK64) ^ mix64(attempt))
