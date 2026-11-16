# Integration Contracts

These documents are the shared boundaries among the engine, external agents and
the desktop client. The MPS Armada assignment
(<https://ocw.cs.pub.ro/courses/mps/proiect>) requires versioned contracts for
the engine–agent protocol, the history file format and the engine command-line
interface, plus documented rules for every situation the assignment leaves
open.

## Versions and status

| Document | Boundary | Version | Status |
| --- | --- | --- | --- |
| [Game models](game-models.md) | Shared domain models, rules, fingerprint | 1 | IMPLEMENTED (frozen in L01) |
| [Agent protocol](agent-protocol.md) | Engine ↔ agent standard streams | 1 | IMPLEMENTED (frozen in L01) |
| [Engine CLI](engine-cli.md) | Client → engine process invocation | 1 | IMPLEMENTED (frozen in L01) |
| [History format](history-format.md) | Engine output consumed by the client | 1 | IMPLEMENTED (frozen in L01) |

Status values: **DRAFT** (not usable), **APPROVED** (frozen, consumers may
depend on it), **IMPLEMENTED** (all producers and consumers exist and pass the
contract tests). All four reached IMPLEMENTED with delivery L10; the evidence is
in `docs/reports/test-report-L11.md`.

> Approval note: the freeze was performed during the L01 delivery under the
> coordinator's instruction to record under-specified values as team decisions.
> Every such value is marked "Team" in the documents. The team coordinator
> should confirm these decisions at the next meeting and record the
> confirmation in the meeting minutes.

## Team decisions (not from the official spec)

| Topic | Decision | Where |
| --- | --- | --- |
| Initial movement budget | 1000 per player, configurable | game-models §2, §4.1 |
| Time and memory limits | 500 ms per tick, 3000 ms init, 512 MB | game-models §4.1, agent-protocol §5 |
| Map symmetry type | 180° rotation | game-models §4.2 |
| Seed range and derived seeds | `0 … 2^64−1`, SplitMix64-based derivation, at most 100 attempts | game-models §2, map generator contract section (L02) |
| Build timing | paid in tick `t`, spawns in `t+1` or later when the base is free | game-models §6.2 |
| Budget accounting | ignored commands cost nothing; ascending ship id order | game-models §6.1, §6.3 |
| Own-base collision exception | ships on a base are never destroyed | game-models §6.5 |
| Early end condition detail | "can still collect" definition | game-models §6.8 |
| Final tie-break rule | fewer invalid commands, then draw | game-models §6.9 |
| Fingerprint | SHA-256 of canonical JSON state | game-models §7 |
| Wire framing | JSON Lines, 65 536-byte agent lines | agent-protocol §2 |
| Stale / malformed / crash handling | see table | agent-protocol §4 |
| CLI shape and exit codes | `python -m neon_armada.engine …` | engine-cli |
| History encoding and event model | single JSON document, event deltas | history-format |

## Change process

A change to any cross-boundary shape requires: a team-approved decision, a
version increment in the affected document and in
`src/neon_armada/contracts/versions.py`, updated fixtures in
`tests/fixtures/contracts/` and passing contract tests in
`tests/unit/contracts/`.

## Freeze checklist (L01)

Exported Python symbols (package `neon_armada.contracts`):

- `versions`: `MODELS_VERSION`, `PROTOCOL_VERSION`, `HISTORY_VERSION`,
  `CLI_VERSION`, `GENERATOR_VERSION` (all `1`).
- `models`: `ContractError`, `Action`, `Ship`, `EnergyCell`, `MatchConfig`,
  `StaticMap`, `MatchState`, `ShipCommand`, `PlayerCommands`, `Exclusion`,
  `MatchResult`, cell characters `CELL_EMPTY`, `CELL_DEPOSIT`, `CELL_OBSTACLE`,
  `CELL_BASES`, and constants `MIN_MAP_SIZE`, `MAX_MAP_SIZE`,
  `INITIAL_BASE_ENERGY`, `SHIP_CAPACITY`, `BUILD_COST`, `MINING_DIVISOR`,
  `MAX_TICKS_LIMIT`, `DEFAULT_MOVE_BUDGET`, `MAX_SEED`,
  `INVALID_REASONS`, `EXCLUSION_REASONS`, `END_REASONS`, `DECIDED_BY`.
- `fingerprint`: `canonical_state_bytes`, `state_fingerprint`.
- `protocol`: `ProtocolError`, `StaleResponseError`, `MAX_AGENT_LINE_BYTES`,
  `MAX_CONSECUTIVE_TIMEOUTS`, `encode_message`, `init_message`,
  `tick_message`, `end_message`, `parse_ready`, `parse_commands`,
  `parse_engine_message`.
- `history`: `HistoryError`, `HISTORY_FORMAT`, `EVENT_FIELDS`,
  `validate_history_document`.
- `cli`: `ExitCode`, `ENGINE_MODULE`.

Checklist:

- [x] Four contracts versioned and cross-referenced.
- [x] Official numeric values separated from team decisions.
- [x] Exact nine-phase tick order recorded (game-models §5).
- [x] Canonical valid and invalid fixtures in `tests/fixtures/contracts/`.
- [x] Contract tests in `tests/unit/contracts/`.
- [ ] Coordinator confirmation of the team decisions recorded in meeting
      minutes (human action).

Known open decisions: none blocking. The map-generator constants (obstacle and
deposit density, energy range, derived-seed formula) are fixed by L02 in the
"Map generator" section of the game-models contract.
