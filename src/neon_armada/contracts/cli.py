"""Engine command-line constants (``contracts/engine-cli.md``, version 1)."""

from __future__ import annotations

from enum import IntEnum

ENGINE_MODULE = "neon_armada.engine"


class ExitCode(IntEnum):
    """Exit codes of ``python -m neon_armada.engine``."""

    OK = 0
    DIFFERENT = 1
    USAGE = 2
    AGENT_NOT_FOUND = 3
    MAP_GENERATION_FAILED = 4
    OUTPUT_ERROR = 5
    HISTORY_INVALID = 6
    INTERNAL_ERROR = 70
