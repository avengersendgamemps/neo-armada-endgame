"""Canonical state serialisation and fingerprint (``game-models.md`` §7)."""

from __future__ import annotations

import hashlib
import json

from neon_armada.contracts.models import MatchState


def canonical_state_bytes(state: MatchState) -> bytes:
    """Return the canonical JSON encoding of ``state``.

    Keys are sorted, there is no whitespace and the output is ASCII, so the
    bytes are identical on every platform for equal states.
    """
    return json.dumps(
        state.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def state_fingerprint(state: MatchState) -> str:
    """Return the SHA-256 fingerprint (lowercase hex) of ``state``."""
    return hashlib.sha256(canonical_state_bytes(state)).hexdigest()
