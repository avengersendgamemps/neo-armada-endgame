# Game Models Contract

**Contract version:** 1 (`MODELS_VERSION = 1`)
**Status:** APPROVED for implementation (L01 freeze) — see [README](README.md)
**Python source of truth:** `src/neon_armada/contracts/models.py`,
`src/neon_armada/contracts/fingerprint.py`

Rules marked **[Official]** come from the MPS Armada assignment
(<https://ocw.cs.pub.ro/courses/mps/proiect>). Rules marked **[Team]** are
**team decisions, not from the official spec**; they resolve situations the
assignment leaves open ("orice situație neacoperită de reguli se rezolvă printr-o
regulă adăugată în documentație").

## 1. Scope

Shared vocabulary and data shapes used by the engine, the agent protocol, the
history format and the desktop client. The models are plain immutable values;
they contain no PySide6, subprocess or file-system behaviour.

## 2. Numeric rules

- **[Official]** The simulation uses integers only and is strictly deterministic.
- **[Official]** Map side: `32 ≤ map_size ≤ 64`, square grid.
- **[Official]** Each player starts with `1000` energy in the base and one ship.
- **[Official]** Ship cargo capacity: `100`.
- **[Official]** Build cost: `500`.
- **[Official]** Mining amount: `ceil(cell_energy / 10)`, limited by free cargo.
- **[Official]** Match length: at most `500` ticks.
- **[Team]** Seed range: `0 ≤ seed ≤ 2^64 − 1`.
- **[Team]** Default initial movement budget: `1000` move commands per player
  for the whole match (`move_budget`, allowed `0 … 1 000 000`).
- **[Team]** `max_ticks` is configurable in `1 … 500` (default `500`) so that
  short matches can be used in tests; it can never exceed the official limit.

## 3. Coordinates, players and identifiers

- **[Team]** Coordinates are `(x, y)` integers, origin `(0, 0)` in the top-left
  corner; `x` grows to the east, `y` grows to the south. North is `y − 1`.
- **[Team]** Canonical cell order is row-major: ascending `y`, then ascending `x`.
- **[Team]** Players are identified by `0` (agent A) and `1` (agent B). Every
  two-element per-player array is indexed by player id.
- **[Team]** Ship ids are non-negative integers, unique for the whole match and
  never reused. The initial ships are `0` (player 0) and `1` (player 1). Later
  ids are assigned from `next_ship_id` when a ship appears; when both players
  spawn in the same tick, player 0 receives the lower id. Id order has no
  gameplay effect other than rule 6.3 (budget order inside one player).
- **[Team]** Canonical ship order is ascending ship id.

## 4. Models

### 4.1 `MatchConfig`

| Field | Type | Default | Range | Origin |
| --- | --- | --- | --- | --- |
| `map_size` | int | 32 | 32 … 64 | Official range, team default |
| `max_ticks` | int | 500 | 1 … 500 | Official limit |
| `move_budget` | int | 1000 | 0 … 1 000 000 | Team |
| `tick_timeout_ms` | int | 500 | 10 … 60 000 | Team |
| `init_timeout_ms` | int | 3000 | 10 … 600 000 | Team |
| `memory_limit_mb` | int | 512 | 16 … 65 536 | Team |

The official page requires a per-tick time limit, a more generous
initialisation limit and a memory limit but gives **no numbers**; the three
limit values above are team decisions.

### 4.2 `StaticMap`

```json
{"size": 32, "cells": ["....#...", "..."], "bases": [[3, 4], [28, 27]]}
```

- `cells` has `size` strings of `size` characters, row `y` at index `y`.
- Cell characters: `.` empty, `*` energy deposit (at generation time),
  `#` obstacle, `0` base of player 0, `1` base of player 1.
- `bases[p]` is the `[x, y]` position of the base of player `p` and must match
  the `0`/`1` characters. Exactly one base per player.
- **[Official]** The map is symmetric. **[Team]** The symmetry is a 180°
  rotation: cell `(x, y)` pairs with `(size − 1 − x, size − 1 − y)`; kinds and
  initial energy are equal for paired cells and bases pair with each other.
- The static map never changes during a match. The `*` marker is the
  generation-time classification; current energy lives in `MatchState.energy`.

### 4.3 `Ship`

```json
{"id": 0, "owner": 0, "x": 3, "y": 4, "cargo": 0}
```

`0 ≤ cargo ≤ 100`.

### 4.4 `MatchState` (dynamic state, also the fingerprint input)

```json
{
  "tick": 0,
  "reserves": [1000, 1000],
  "move_budgets": [1000, 1000],
  "pending_builds": [false, false],
  "invalid_commands": [0, 0],
  "next_ship_id": 2,
  "ships": [{"id": 0, "owner": 0, "x": 3, "y": 4, "cargo": 0}],
  "energy": [[10, 2, 350]]
}
```

- `tick` is the number of completed ticks (`0` for the initial state).
- `energy` lists every cell with energy `> 0` as `[x, y, energy]` in row-major
  order. Cells that are absent hold `0`.
- `ships` is in ascending id order.
- `invalid_commands[p]` is the running count of ignored commands of player `p`
  (it is state because it takes part in the tie-break, rule 6.9).

### 4.5 `PlayerCommands`

One optional action per ship (`N`, `S`, `E`, `W`, `STAY`) plus one optional base
`build` request per tick. See the [agent protocol](agent-protocol.md).

### 4.6 `MatchResult`

```json
{
  "end_reason": "tick_limit",
  "ticks_played": 500,
  "winner": 0,
  "decided_by": "score",
  "scores": [2300, 1900],
  "ships_remaining": [2, 1],
  "carried_energy": [40, 0],
  "invalid_commands": [0, 3],
  "timeouts": [0, 1],
  "collisions": 1,
  "exclusions": [null, {"tick": 17, "reason": "timeout"}]
}
```

- `end_reason`: `tick_limit` or `budgets_exhausted`.
- `winner`: `0`, `1` or `null` (draw).
- `decided_by`: `score`, `ships_remaining`, `carried_energy`,
  `invalid_commands` or `draw`.
- `collisions`: number of collision events (cells), not destroyed ships.
- `exclusions[p]`: `null`, or the tick and reason of the exclusion
  (`init_timeout`, `init_failed`, `timeout`, `crashed`). Tick `0` means the
  agent was excluded during initialisation.

## 5. Tick order

**[Official]** Every tick is processed in exactly this order:

1. send the visible state to every agent;
2. read commands within the time limit;
3. validate commands and drop invalid ones;
4. build new ships;
5. move all ships simultaneously;
6. resolve collisions;
7. mining by ships that stayed in place;
8. deliver cargo in bases;
9. update budgets, compute the state fingerprint, write history events.

## 6. Rules and team clarifications

### 6.1 Validation (phase 3)

Validation uses the state **before** the tick. Each ignored command increments
`invalid_commands[player]` and produces an `invalid_command` history event.

| Reason | Situation | Origin |
| --- | --- | --- |
| `out_of_bounds` | move outside the map | Official |
| `obstacle` | move into an obstacle | Official |
| `enemy_base` | move onto the opponent's base | Official |
| `no_budget` | move command when the remaining budget cannot cover it | Team (official: ships stay) |
| `unknown_ship` | ship id does not exist or belongs to the opponent | Team |
| `duplicate_ship` | second and later commands for the same ship in one tick | Team |
| `malformed_entry` | a move entry that is not `{ship:int, action:str}` with a known action | Team |
| `build_insufficient_energy` | build with reserve `< 500` | Team |
| `build_already_pending` | build while an earlier build is still waiting | Team |

- **[Team]** A ship without a command stays in place; this is not an error.
- **[Team]** An ignored command consumes **no** movement budget.

### 6.2 Construction (phase 4) — build timing

**[Official]** A build command costs 500 and makes a new ship appear on the base
cell in the next tick, if the base is free. **[Team]** Exact schedule:

1. First, a pending build from an earlier tick is resolved: if no ship stands
   on the owner's base at this moment, the new ship appears there with cargo
   `0` (event `ship_spawned`); otherwise the build stays pending and is retried
   in the construction phase of every following tick.
2. Then, a build command accepted in phase 3 of this tick is paid:
   `reserves[p] −= 500`, `pending_builds[p] = true` (event `build_started`).

So a build ordered in tick `t` spawns in tick `t + 1` at the earliest. At most
one build per player can be pending. A ship that appears in tick `t` cannot be
commanded in tick `t` (the agent has not observed it yet). A build still pending
when the match ends is lost (the energy stays spent).

### 6.3 Movement budget

**[Official]** Each move command (`N`/`S`/`E`/`W`) consumes one unit of the
player's budget; staying is free; when the budget is exhausted ships stay.
**[Team]** Otherwise-valid move commands of one player are charged in ascending
ship id order; when the budget reaches `0` the remaining move commands of that
tick are ignored with reason `no_budget`.

### 6.4 Simultaneous movement (phase 5)

All accepted moves are applied at the same time from the pre-tick positions.
No player or ship is resolved before another.

### 6.5 Collisions (phase 6)

- **[Official]** If two or more ships are in the same cell after movement, all
  of them are destroyed regardless of owner and their cargo is added to the
  cell. Two ships that swap cells do not collide.
- **[Official]** Exception: the own base. **[Team]** Formalisation: ships on a
  base cell are never destroyed by a collision; any number of ships of the
  owner may share their own base cell. (Opponent ships can never be there,
  because moving onto the opponent's base is an invalid move.)
- **[Team]** The cargo is added to the cell even if it was an empty cell; any
  non-base cell with energy `> 0` can be mined afterwards.

### 6.6 Mining (phase 7)

**[Official]** A surviving ship that did not change cell this tick and stands on
a cell with energy `e > 0` collects `min(ceil(e / 10), 100 − cargo)`.
**[Team]** "Did not change cell" includes ships whose move was ignored, ships
without a command and ships of timed-out or excluded agents. A ship that
appeared this tick stands on a base and base cells never hold energy.

### 6.7 Delivery (phase 8)

**[Official]** A ship on its own base hands over its whole cargo to the reserve.

### 6.8 End of match

**[Official]** The match ends after `max_ticks` ticks (`tick_limit`), or earlier
when both players have exhausted their budget and no ship can still collect
(`budgets_exhausted`). **[Team]** "Can still collect" means: a ship with free
cargo space stands on a non-base cell with energy `> 0`. The check runs after
phase 8 of every tick. Excluded agents keep their unused budget, so a match
with an excluded agent normally runs to the tick limit.

### 6.9 Score and tie-break

**[Official]** Score = base reserve at the end. Ties are broken, in order, by
(1) more ships remaining, (2) more carried energy, (3) a fixed documented rule.
**[Team]** Fixed rule: (3) fewer invalid commands wins; (4) if still equal the
match is a draw (`winner = null`). No rule depends on the player index.

## 7. State fingerprint

**[Official]** A value computed from the game state at every tick, stored in the
history. **[Team]** Algorithm (version 1): SHA-256, lowercase hexadecimal, of
the canonical JSON encoding of the `MatchState` object of section 4.4:

- keys sorted alphabetically at every level;
- no whitespace (separators `,` and `:`), ASCII only;
- `ships` in ascending id order, `energy` in row-major order;
- integers in decimal, booleans as `true`/`false`.

Timestamps, paths, process ids, agent names and timing data are never hashed.

## 8. Validation errors

`from_dict` constructors raise `ContractError` (a `ValueError`) with a message
that names the offending field. Booleans are not accepted where integers are
required. Unknown keys are ignored for forward compatibility.

## 9. Map generator (`GENERATOR_VERSION = 1`)

**Python source of truth:** `src/neon_armada/engine/world/rng.py`,
`src/neon_armada/engine/world/generator.py`.

**[Official]** The map is generated from the integer seed by an algorithm fixed
in the contract; one half is produced and mirrored or rotated for the other
player; after generation the engine checks by traversal that every deposit can
be reached from both bases; otherwise a new map is generated deterministically
from a derived seed. The same seed always produces the same map.
Everything below is a **team decision, not from the official spec**.

### 9.1 PRNG

SplitMix64 over unsigned 64-bit integers, state initialised with the seed:

```text
state = (state + 0x9E3779B97F4A7C15) mod 2^64
z = state
z = ((z xor (z >> 30)) * 0xBF58476D1CE4E5B9) mod 2^64
z = ((z xor (z >> 27)) * 0x94D049BB133111EB) mod 2^64
next = z xor (z >> 31)
below(n) = next mod n
mix64(v) = first output of a generator seeded with v
```

### 9.2 Derived seeds and retry policy

`map_seed(seed, 0) = seed`; for attempt `k ≥ 1`:
`map_seed(seed, k) = mix64(seed xor mix64(k))`. Attempts `0, 1, 2, …` are tried
in order and the first valid candidate is used. After `100` invalid candidates
generation fails (`MapGenerationError`, CLI exit code 4). The accepted
`map_seed` and attempt index are stored in the history header.

### 9.3 Candidate algorithm

For side `size` and PRNG seeded with `map_seed`, with constants obstacle `12 %`,
deposit `6 %`, deposit energy `50 … 500`:

1. `base0 = (1 + below(size div 4), 1 + below(size div 4))` (x drawn first);
   `base1` is its 180° rotation `(size − 1 − x, size − 1 − y)`.
2. Visit the first `(size · size) div 2` cells in row-major order (for an odd
   side the centre cell is never visited and stays empty). A cell within
   Chebyshev distance 1 of either base stays empty and draws nothing.
   Otherwise `roll = below(100)`: `roll < 12` → obstacle; `roll < 18` →
   deposit with energy `50 + below(451)`; else empty. The same kind and energy
   are written to the rotated partner cell.
3. The base cells are written last.

### 9.4 Validity

A candidate is valid when it contains at least one deposit and, for each
player, a breadth-first search from the player's base over 4-neighbour moves —
not entering obstacles or the opponent's base (ships can never enter either) —
reaches every deposit cell.
