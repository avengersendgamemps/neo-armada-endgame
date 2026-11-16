# Engine CLI Contract

**Contract version:** 1 (`CLI_VERSION = 1`)
**Status:** APPROVED for implementation (L01 freeze) — see [README](README.md)
**Python source of truth:** `src/neon_armada/contracts/cli.py`

**[Official]** The engine is a command-line program that receives the players'
scripts, the seed and parameters, and writes the match history to a file. The
client starts it as a separate process; there is no persistent connection,
shared memory or direct function call between them. The contract defines the
accepted arguments, the exit codes and where the result file is written.
Everything else below is a **team decision, not from the official spec**.

## 1. Invocation

```text
python -m neon_armada.engine <command> [options]
```

### 1.1 `run` — play one match

```text
python -m neon_armada.engine run --agent-a PATH --agent-b PATH --seed N --output FILE
        [--name-a TEXT] [--name-b TEXT]
        [--map-size 32..64] [--max-ticks 1..500] [--move-budget N]
        [--tick-timeout-ms N] [--init-timeout-ms N] [--memory-limit-mb N]
```

| Option | Required | Meaning |
| --- | --- | --- |
| `--agent-a`, `--agent-b` | yes | Path of the agent program for player 0 / player 1 |
| `--seed` | yes | Integer `0 … 2^64 − 1` |
| `--output` | yes | Path of the history file to write |
| `--name-a`, `--name-b` | no | Display names stored in the history (default: file name without extension) |
| other options | no | `MatchConfig` fields, defaults from the game-models contract |

**Agent launch rule.** An agent path ending in `.py` is started as
`<engine python interpreter> -u PATH`; any other path is executed directly as a
program. Paths are passed as argument lists, never through a shell; spaces in
paths are supported. The agent's working directory is the directory containing
the agent file.

**Output rule.** Missing parent directories are created. An existing file is
overwritten. The file is written to a temporary sibling and renamed at the end,
so a reader never observes a partial history. The history contains no absolute
paths.

### 1.2 `validate` — check one history file

```text
python -m neon_armada.engine validate HISTORY
```

Reads the file, reconstructs every tick from the recorded events and compares
each reconstructed state with the recorded fingerprint.

### 1.3 `compare` — determinism check of two histories

```text
python -m neon_armada.engine compare HISTORY_A HISTORY_B
```

Compares headers (seed, configuration, map) and fingerprints tick by tick and
reports the first tick that differs.

### 1.4 `check-determinism` — run a match twice and compare

```text
python -m neon_armada.engine check-determinism --agent-a PATH --agent-b PATH --seed N
        [--output-dir DIR] [same optional options as run]
```

## 2. Standard streams

- **stdout:** exactly one line, a JSON object, written when the command ends.
- **stderr:** human-readable diagnostics. Nothing else is written to stdout.

`run` success:

```json
{"status": "ok", "cli_version": 1, "history": "out/match.json",
 "result": { "...": "MatchResult" },
 "timing": {"total_ms": 812, "agent_wait_ms": [301, 322], "engine_ms": 189}}
```

`timing` is diagnostic, non-deterministic and never stored in the history.

`compare` / `check-determinism`:

```json
{"status": "ok", "cli_version": 1, "identical": false,
 "first_divergent_tick": 37, "detail": "fingerprint mismatch"}
```

`first_divergent_tick` is `null` when identical, `0` when the headers, maps or
initial states already differ.

`validate`:

```json
{"status": "ok", "cli_version": 1, "valid": true, "ticks": 500}
```

Errors (any command):

```json
{"status": "error", "cli_version": 1, "code": 3, "message": "agent not found: x.py"}
```

## 3. Exit codes

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | `OK` | Command succeeded (match completed, histories identical, history valid). A match in which agents timed out or were excluded still completes with 0. |
| 1 | `DIFFERENT` | `compare` / `check-determinism`: the runs diverge; `validate`: fingerprints do not match the reconstruction |
| 2 | `USAGE` | Invalid or missing arguments, values out of range |
| 3 | `AGENT_NOT_FOUND` | An agent path does not exist or is not a file |
| 4 | `MAP_GENERATION_FAILED` | No valid map within the retry limit |
| 5 | `OUTPUT_ERROR` | The history file cannot be written |
| 6 | `HISTORY_INVALID` | A history file is missing, corrupt, truncated or has an unsupported version |
| 70 | `INTERNAL_ERROR` | Unexpected engine failure |

## 4. Versioning

`cli_version` is reported in every stdout object. Removing or changing the
meaning of an option, output field or exit code increments the version.
