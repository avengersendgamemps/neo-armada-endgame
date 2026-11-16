"""Replay controller: playback position, speed and transport state.

Pure Python on purpose: no Qt, no history parsing, no game rules. The
controller only knows how many ticks a match has and where playback currently
is. The position is a real number of ticks: its integer part selects the
recorded state to show and its fractional part is the interpolation progress
towards the next one, so playback timing never touches simulation state.

Client presentation decision (not from the official spec, not a contract):
normal speed shows ``BASE_TICKS_PER_SECOND`` ticks per second; x2 and x4
multiply it.
"""

from __future__ import annotations

import math

SPEEDS = (1, 2, 4)
BASE_TICKS_PER_SECOND = 5.0


class ReplayController:
    """Transport state of one loaded match (``last_tick`` 0 means nothing to play)."""

    def __init__(
        self, last_tick: int = 0, ticks_per_second: float = BASE_TICKS_PER_SECOND
    ) -> None:
        if ticks_per_second <= 0:
            raise ValueError("ticks_per_second must be positive")
        self._ticks_per_second = float(ticks_per_second)
        self._speed = SPEEDS[0]
        self._last_tick = 0
        self._position = 0.0
        self._playing = False
        self.load(last_tick)

    # -- state ------------------------------------------------------------------

    @property
    def last_tick(self) -> int:
        return self._last_tick

    @property
    def position(self) -> float:
        """Playback position in ticks, within ``0..last_tick``."""
        return self._position

    @property
    def tick(self) -> int:
        """The recorded state currently shown (integer part of the position)."""
        return int(self._position)

    @property
    def progress(self) -> float:
        """Interpolation progress towards ``tick + 1``, within ``[0, 1)``."""
        return self._position - int(self._position)

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def at_end(self) -> bool:
        return self._position >= self._last_tick

    # -- commands ---------------------------------------------------------------

    def load(self, last_tick: int) -> None:
        """Start over, paused at tick 0, for a match with ``last_tick`` ticks.

        The selected speed is kept.
        """
        if last_tick < 0:
            raise ValueError("last_tick must not be negative")
        self._last_tick = int(last_tick)
        self._position = 0.0
        self._playing = False

    def play(self) -> None:
        """Start playback; from the beginning if the match is at its end."""
        if self._last_tick == 0:
            return
        if self.at_end:
            self._position = 0.0
        self._playing = True

    def pause(self) -> None:
        self._playing = False

    def toggle(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def step(self) -> None:
        """Pause and show the next whole tick (stays on the last one)."""
        self._playing = False
        self._position = float(min(self._last_tick, self.tick + 1))

    def seek(self, tick: int) -> None:
        """Jump to a whole tick, clamped to the match.

        Playback continues from there if it was running, except at the last
        tick, where there is nothing left to play.
        """
        self._position = float(max(0, min(self._last_tick, int(tick))))
        if self.at_end:
            self._playing = False

    def set_speed(self, speed: int) -> None:
        if speed not in SPEEDS:
            raise ValueError(f"speed must be one of {SPEEDS}")
        self._speed = speed

    def advance(self, elapsed_seconds: float) -> bool:
        """Move playback forward by wall-clock time; return whether it moved.

        Playback pauses by itself on the last tick.
        """
        if not self._playing:
            return False
        if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0:
            return False
        self._position += elapsed_seconds * self._speed * self._ticks_per_second
        if self._position >= self._last_tick:
            self._position = float(self._last_tick)
            self._playing = False
        return True
