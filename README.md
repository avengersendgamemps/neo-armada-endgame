# Neon Armada: Endgame

**Team:** Avengers Endgame
**Status:** deliveries L01–L12 implemented on `feature/L*` branches (see
[roadmap](docs/planning/roadmap.md)); not yet merged into `main`.

Neon Armada: Endgame is the team's implementation of the MPS "Armada" assignment
(<https://ocw.cs.pub.ro/courses/mps/proiect>): a deterministic two-player strategy
simulation in which each player is an autonomous program. It consists of

- a **headless engine** that runs a match between two agent programs and writes its
  complete history to a file;
- **agent starter kits** in Python and C++17, a reference agent and the team's own agent;
- a **desktop client** (PySide6) that starts matches and replays history files.

The engine and the client run on the same computer and are connected only by the engine's
command line and the history file.

## Team

> **TODO (team):** list the team members and their roles here. The repository does not
> record the roster; the assignment asks for 7–8 members. Role definitions are in
> [docs/planning/team-roles.md](docs/planning/team-roles.md).

| Member | Role |
| --- | --- |
| TODO | TODO |

## Technology and external dependencies

| Area | Choice |
| --- | --- |
| Engine, client, tests | Python 3.11 or newer (developed and tested with 3.12.10) |
| GUI | PySide6 6.6 or newer (tested with 6.12.0) — the only runtime dependency |
| Agents | Python (standard library only) and C++17 (standard library only) |
| C++ build | CMake 3.20 or newer with GCC, Clang or MSVC |
| Tests and lint | pytest 8, Ruff |
| CI | `.gitlab-ci.yml` (lint, C++ build, tests) — see [limitations](#known-limitations) |

No other external solution, service or library is used. Rules, file formats and graphics
are the team's own.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
cmake -S agents/cpp -B build/cpp      # optional: C++ starter agent
cmake --build build/cpp
```

Use `python3` where `python` is not available. Supported and tested: Windows 11.
Linux and macOS are expected to work but were not tested (on macOS the agent memory
limit is not applied).

## Running a match from the command line

```bash
python -m neon_armada.engine run \
    --agent-a agents/python/team_agent.py \
    --agent-b agents/python/reference_agent.py \
    --seed 42 --map-size 32 --output histories/match-42.history.json
```

The engine prints one JSON line with the result and exits with code 0. Other commands:

```bash
python -m neon_armada.engine validate HISTORY            # rebuild every tick, check fingerprints
python -m neon_armada.engine compare HISTORY_A HISTORY_B  # first tick that differs
python -m neon_armada.engine check-determinism --agent-a A --agent-b B --seed 42
```

All options, output and exit codes: [contracts/engine-cli.md](contracts/engine-cli.md).

## Desktop client

```bash
python -m neon_armada.client                      # empty window
python -m neon_armada.client HISTORY              # open a history
python -m neon_armada.client --agent-a A --agent-b B --seed 42   # start a match at once
```

- **File > New match** (Ctrl+N): choose two local agent scripts or executables, a seed
  and the map size. The engine is started as a separate process; when it finishes, the
  history opens automatically. Closing the client does not stop a running match.
- **File > Open history** (Ctrl+O): replay any history file.
- **Replay bar:** Play/Pause (Space), Next tick (N), speed x1 / x2 / x4, timeline slider.
  At x1 the replay shows 5 ticks per second.
- New histories are written to `histories/` in the current directory unless another
  file is chosen; the engine's output is kept next to them (`*.engine-stdout.json`,
  `*.engine-stderr.log`).

## Agents

Agents are ordinary programs that talk to the engine over standard input and output.
See [agents/README.md](agents/README.md) for the starter kits and
[contracts/agent-protocol.md](contracts/agent-protocol.md) for the protocol.

| Agent | Path |
| --- | --- |
| Team agent | `agents/python/team_agent.py` |
| Reference agent | `agents/python/reference_agent.py` |
| Python starter template | `agents/python/starter_agent.py` |
| C++ starter agent | `build/cpp/bin/neon_starter_agent` (after the CMake build) |

## Quality checks

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python scripts/collect_metrics.py        # engine time, determinism, game metrics
python scripts/benchmark_gui.py HISTORY  # replay frame rate
```

Measured results: [docs/reports/test-report-L11.md](docs/reports/test-report-L11.md).

## Repository layout

```text
src/neon_armada/contracts/   shared models, protocol, history schema, fingerprint, reader
src/neon_armada/engine/      map generator, mechanics, agent runtime, match loop, CLI
src/neon_armada/client/      PySide6 client: adapter, map view, replay, launcher
agents/                      Python and C++17 starter kits, reference and team agents
contracts/                   versioned contracts and the team's rule decisions
tests/                       unit, integration, determinism and end-to-end tests
scripts/                     measurement scripts
docs/                        design document, planning, reports, demo script
coding-style/                team Python and C++ standards
```

## Documentation

- Versioned contracts and additional rules: [contracts/](contracts/README.md)
- Software Design Document: [docs/architecture/SDD.md](docs/architecture/SDD.md)
- Roadmap, backlog, roles: [docs/planning/](docs/planning/roadmap.md)
- Test report: [docs/reports/test-report-L11.md](docs/reports/test-report-L11.md)
- Demo script: [docs/demo-script.md](docs/demo-script.md)
- Templates: [meetings](docs/meetings/template.md),
  [test reports](docs/reports/test-report-template.md),
  [architecture decisions](docs/architecture/decisions/template.md)

## Development methodology and workflow

> **TODO (team):** state the methodology the team actually follows (for example Scrum
> or Kanban, sprint length, ceremonies) and link the board.

What the repository defines: work is tracked as Epic → Story → Task → Branch → Merge
Request ([backlog format](docs/planning/backlog.md)); issue and merge-request templates
are in `.gitlab/`; changes go through review; branch names follow
`feature/MPS-XXX-description` (also `bugfix/`, `test/`, `docs/`, `chore/`, `ci/`).

## Project management evidence

The assignment asks for planning artefacts, a communication plan, meeting minutes and a
dashboard. These must come from the team's real records and are **not in the repository
yet**:

| Item | State |
| --- | --- |
| Dashboard with tickets, Gantt chart, burndown chart | TODO (team) — link it here |
| Communication plan | TODO (team) |
| Meeting minutes (decisions, actions, owners, deadlines) | TODO (team) — only the [template](docs/meetings/template.md) exists |
| Estimated versus actual time per task | TODO (team) |
| Coordinator confirmation of the team rule decisions in `contracts/` | TODO (team) — record in meeting minutes |

## AI assistance disclosure

The code, tests and documents of deliveries L01–L12 on the `feature/L*` branches were
produced with an AI coding assistant (Claude Code) directed by a team member; those
commits carry a `Co-Authored-By: Claude` trailer. The team is responsible for reviewing
them and for completing this disclosure as the course policy requires.

## Known limitations

- Tested on Windows 11 only.
- The CI file is for GitLab, while the repository's remote is on GitHub; no pipeline run
  was verified.
- Agents are trusted programs: time and memory limits protect the engine from faulty
  agents, not from hostile code. On macOS no memory limit is applied.
- The optional features of the assignment (code editor, campaign, advanced effects,
  charts, batch runs, leaderboard, manual agent, rule variants) are not implemented.
