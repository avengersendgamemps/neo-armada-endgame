# Agent Protocol Contract

**Contract version:** 1 (`PROTOCOL_VERSION = 1`)
**Status:** APPROVED for implementation (L01 freeze) — see [README](README.md)
**Python source of truth:** `src/neon_armada/contracts/protocol.py`

**[Official]** items come from the MPS Armada assignment, section *Agenți* and
*Contractele de comunicare*. **[Team]** items are **team decisions, not from the
official spec** (the page defines neither the wire format nor numeric limits).

## 1. Processes and streams

- **[Official]** An agent is any program that can be started from the command
  line. The engine starts each agent as a separate process, writes the state to
  the agent's standard input and reads commands from its standard output.
- **[Team]** Standard output carries protocol messages only. Diagnostics go to
  standard error; the engine drains stderr and keeps at most the last 64 KiB.
- **[Team]** Agents are trusted; limits protect the engine from faults, not from
  hostile code.

## 2. Framing

**[Team]** JSON Lines: every message is one JSON object encoded as UTF-8 on a
single line terminated by `\n` (a preceding `\r` is tolerated). The agent must
flush stdout after every message. A line from an agent may be at most
`65 536` bytes including the terminator; longer lines are malformed. Unknown
object keys are ignored. Every message has a string field `type`.

## 3. Message sequence

```text
engine -> agent : init
agent  -> engine: ready                 (within init_timeout_ms)
repeat for tick = 1, 2, ...:
    engine -> agent : tick
    agent  -> engine: commands          (within tick_timeout_ms)
engine -> agent : end
```

### 3.1 `init` (engine → agent)

**[Official]** Sent once, contains the static map.

```json
{"type": "init", "protocol_version": 1, "player_id": 0,
 "config": {"map_size": 32, "max_ticks": 500, "move_budget": 1000,
            "tick_timeout_ms": 500, "init_timeout_ms": 3000,
            "memory_limit_mb": 512},
 "map": {"size": 32, "cells": ["...", "..."], "bases": [[3, 4], [28, 27]]}}
```

`config` and `map` are the `MatchConfig` and `StaticMap` models of the
[game-models contract](game-models.md).

### 3.2 `ready` (agent → engine)

```json
{"type": "ready", "protocol_version": 1}
```

The agent must answer within `init_timeout_ms`, measured from process start
(**[Official]**: the first initialisation gets a more generous limit).

### 3.3 `tick` (engine → agent)

**[Official]** Only dynamic state: ship positions, cell energy, base reserves.
**[Team]** Both agents see the complete state of both players.

```json
{"type": "tick", "tick": 1,
 "reserves": [1000, 1000], "move_budgets": [1000, 1000],
 "pending_builds": [false, false],
 "ships": [{"id": 0, "owner": 0, "x": 3, "y": 4, "cargo": 0},
           {"id": 1, "owner": 1, "x": 28, "y": 27, "cargo": 0}],
 "energy": [[10, 2, 350], [21, 29, 350]]}
```

`tick` is the number of the tick being decided (first tick is `1`). The other
fields have the meaning and ordering of `MatchState`.

### 3.4 `commands` (agent → engine)

**[Official]** One command for each ship; the base may receive a build command.

```json
{"type": "commands", "tick": 1,
 "moves": [{"ship": 0, "action": "E"}],
 "build": false}
```

- `tick` (required) must equal the tick being answered.
- `moves` (required) is a list of `{ "ship": <id>, "action": <"N"|"S"|"E"|"W"|"STAY"> }`.
  Ships that are not listed stay in place.
- `build` (optional, default `false`) requests one ship (cost 500).

### 3.5 `end` (engine → agent)

```json
{"type": "end", "reason": "finished", "winner": 0, "scores": [2300, 1900]}
```

`reason` is `finished` (normal end), `excluded` (this agent was excluded) or
`error` (the engine is aborting). `winner` and `scores` are present only for
`finished`. After `end` the agent should exit; the engine closes the agent's
stdin, waits up to 500 ms and then terminates the process.

## 4. Error behaviour

| Situation | Engine behaviour | Origin |
| --- | --- | --- |
| No `commands` line within `tick_timeout_ms` | Tick is lost, the agent's ships stay; counted as a timeout | Official |
| Three consecutive timeouts | Agent is excluded (`timeout`), the match continues | Official |
| Line is not valid JSON, not an object, wrong `type`, missing/ill-typed `tick` or `moves`, `tick` greater than the current tick, or longer than 65 536 bytes | Whole response ignored, ships stay, `invalid_commands += 1`, event `malformed_response`; it is **not** a timeout and resets the consecutive-timeout counter | Official (ignored and counted) + Team (details) |
| `commands` with `tick` lower than the current tick | Stale answer of an earlier timed-out tick: silently discarded, the engine keeps waiting within the same deadline | Team |
| Individual bad move entry / illegal command | Only that command is ignored and counted (game-models §6.1) | Official |
| stdout closed / process exited before `end` | Agent is excluded (`crashed`) at the current tick | Team |
| No valid `ready` within `init_timeout_ms` | Excluded at tick 0 (`init_timeout`) | Team |
| `ready` malformed or with a different `protocol_version`, or the process cannot be started | Excluded at tick 0 (`init_failed`) | Team |
| Memory limit exceeded | The operating system refuses the allocation or ends the process; the engine observes this as `crashed` | Team |

**[Official]** An excluded agent stays in the history with the reason and the
tick of the exclusion; its ships remain on the map and stay in place.
A valid response (even with zero moves) resets the consecutive-timeout counter.

## 5. Limits

| Limit | Default | Origin |
| --- | --- | --- |
| Per-tick response time | `tick_timeout_ms = 500` | Team value |
| Initialisation time | `init_timeout_ms = 3000` | Team value |
| Memory | `memory_limit_mb = 512` | Team value |
| Consecutive timeouts before exclusion | 3 | Official |
| Agent line length | 65 536 bytes | Team |

Memory limits are enforced with operating-system facilities where available
(Windows Job Objects, POSIX `RLIMIT_AS`); see the engine runtime documentation
for platform caveats. This is not a sandbox.

## 6. Versioning

`protocol_version` is an integer. Any change to message shapes or semantics
increments it and updates the fixtures in `tests/fixtures/contracts/`.
An agent that receives an unsupported version should write a diagnostic to
stderr and exit with a non-zero code.
