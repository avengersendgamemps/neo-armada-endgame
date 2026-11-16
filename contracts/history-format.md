# Match History Format Contract

**Contract version:** 1 (`HISTORY_VERSION = 1`)
**Status:** APPROVED for implementation (L01 freeze) — see [README](README.md)
**Python source of truth:** `src/neon_armada/contracts/history.py`

**[Official]** The history is the standardised file that contains everything
needed to reconstruct the match: a header with the format version, the seed,
the parameters and the agent names; the initial state; the events of every
tick; the state fingerprints; the final result. An excluded agent stays in the
history with the reason and the tick of exclusion. The concrete encoding below
is a **team decision, not from the official spec**.

## 1. File

One UTF-8 JSON document (no byte-order mark), conventionally named
`*.history.json`. Integers only; no floating-point numbers, timestamps,
absolute paths or process ids. Unknown keys are ignored by readers.

## 2. Top-level object

```json
{
  "format": "neon-armada-history",
  "history_version": 1,
  "header": {
    "models_version": 1,
    "protocol_version": 1,
    "generator_version": 1,
    "seed": 42,
    "map_seed": 42,
    "map_attempt": 0,
    "config": {"map_size": 32, "max_ticks": 500, "move_budget": 1000,
               "tick_timeout_ms": 500, "init_timeout_ms": 3000,
               "memory_limit_mb": 512},
    "agents": [{"player_id": 0, "name": "reference_agent"},
               {"player_id": 1, "name": "team_agent"}]
  },
  "map": {"size": 32, "cells": ["..."], "bases": [[3, 4], [28, 27]]},
  "initial_state": {"tick": 0, "...": "MatchState"},
  "initial_fingerprint": "<64 hex chars>",
  "setup_events": [],
  "ticks": [
    {"tick": 1, "events": [{"type": "ship_moved", "ship": 0, "x": 4, "y": 4}],
     "fingerprint": "<64 hex chars>"}
  ],
  "result": {"...": "MatchResult"}
}
```

- `seed` is the seed given on the command line; `map_seed` is the derived seed
  of the accepted map and `map_attempt` its retry index (`0` = first try).
- `map`, `initial_state` and `result` are the `StaticMap`, `MatchState` and
  `MatchResult` models of the [game-models contract](game-models.md).
- `setup_events` holds events that happen before tick 1 (only
  `agent_excluded` during initialisation).
- `ticks[i].tick == i + 1`; the list has exactly `result.ticks_played` entries.
- `fingerprint` is the fingerprint (game-models §7) of the state **after** the
  tick; `initial_fingerprint` is that of `initial_state`.

## 3. Events

Events of one tick are listed in tick-phase order. Inside a phase they follow
ascending player id (`invalid_command` events of one player keep validation
order: malformed entries, command-list order, budget, build), ascending ship
id for ship events and row-major cell order for collisions. Each
event is an object with a string `type`. The "state effect" column is
normative: applying the effects of all events of a tick, in order, to the
previous state and then setting `state.tick` to the tick number yields exactly
the next state. No game rule is needed to replay a history.

| Phase | `type` | Fields | State effect |
| --- | --- | --- | --- |
| 2 | `timeout` | `player`, `consecutive` | none |
| 2 | `malformed_response` | `player` | `invalid_commands[player] += 1` |
| 2 | `agent_excluded` | `player`, `reason` | none |
| 3 | `invalid_command` | `player`, `reason`, optional `ship` | `invalid_commands[player] += 1` |
| 4 | `ship_spawned` | `player`, `ship`, `x`, `y` | add ship with cargo 0; `pending_builds[player] = false`; `next_ship_id = ship + 1` |
| 4 | `build_started` | `player`, `cost` | `reserves[player] −= cost`; `pending_builds[player] = true` |
| 5 | `ship_moved` | `ship`, `x`, `y` | ship position becomes `(x, y)`; `move_budgets[owner] −= 1` |
| 6 | `collision` | `x`, `y`, `ships` (ids), `energy_added` | remove the ships; `energy[x, y] += energy_added` |
| 7 | `mined` | `ship`, `amount` | `ship.cargo += amount`; energy of the ship's cell `−= amount` |
| 8 | `delivered` | `ship`, `amount` | `reserves[owner] += amount`; `ship.cargo = 0` |

`reason` values are listed in game-models §6.1 (`invalid_command`) and §4.6
(`agent_excluded`). `timeout`, `malformed_response` and `agent_excluded` are
runtime facts and may differ between runs with non-deterministic agents;
everything else is a pure function of the seed, configuration and commands.

## 4. Validation and compatibility

A reader must reject, with a clear error:

- a file that is not valid JSON or not an object (corrupt/truncated);
- a `format` other than `neon-armada-history`;
- a `history_version` it does not support (version 1 readers accept only `1`);
- missing or ill-typed mandatory fields, non-consecutive tick numbers,
  fingerprints that are not 64 lowercase hexadecimal characters, unknown event
  types or events with missing fields.

Full verification additionally reconstructs each tick and compares the
fingerprint (`python -m neon_armada.engine validate`).

Adding optional fields keeps version 1. Changing or removing fields, event
semantics or the fingerprint algorithm requires `history_version` 2.

## 5. Determinism comparison

Two histories are *identical for determinism* when `seed`, `config`, `map`,
`initial_fingerprint` and every tick fingerprint are equal. The first tick with
a different fingerprint (or `0` if the header/map/initial state differ, or the
first tick missing from the shorter history) is the first divergent tick.
Agent names are not compared.
