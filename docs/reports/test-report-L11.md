# Test Report — L11 quality, regression and performance

- **Tested component:** whole product (engine, agents, history, desktop client) at delivery L11
- **Test environment:** Windows 11 (10.0.26200), Intel64 Family 6 Model 183, Python 3.12.10,
  PySide6 6.12.0, MSVC (Visual Studio 2022) with CMake 4.1.2, 165 Hz display
- **Date:** 2026-11-16
- **Responsible member:** TODO (to be filled in by the team; not recorded in the repository)

Everything below was measured or executed on the environment above on the date above.
Nothing was run on Linux or macOS and nothing was run in a GitLab pipeline; those
items are listed as not verified.

## How to reproduce

```bash
python -m pip install -e ".[dev]"
cmake -S agents/cpp -B build/cpp && cmake --build build/cpp
python -m pytest                      # all automated tests
python -m ruff check . && python -m ruff format --check .
python scripts/collect_metrics.py --seeds 1-10 --map-sizes 32,48,64 --output-dir metrics-out
python scripts/benchmark_gui.py HISTORY_32 HISTORY_48 HISTORY_64 --seconds 10
```

## Automated test run

| Command | Result |
| --- | --- |
| `python -m pytest` (C++ starter agent built) | 471 passed, 0 failed, 0 skipped, 52 s |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 85 files already formatted |
| `cmake -S agents/cpp -B build/cpp && cmake --build build/cpp` | `neon_starter_agent.exe` built |

Without the C++ build, the tests that need the C++ agent are skipped (8 tests), not failed.

| Suite | Tests | What it covers |
| --- | --- | --- |
| `tests/unit/contracts` | 144 | models, protocol messages, history schema, fingerprint, reconstruction from events |
| `tests/unit/world` | 62 | map generator: size, symmetry, reachability from both bases, derived-seed retry |
| `tests/unit/core` | 63 | tick mechanics: move, budget, collisions, swaps, mining, deposit, build, end, tie-break |
| `tests/unit/agents`, `tests/integration/test_agent_protocol_smoke.py` | 35 | Python and C++ starter kits, reference and team agents over the real protocol |
| `tests/integration/test_agent_runtime.py` | 26 | slow, silent, crashing, malformed, flooding, memory-hungry agents; three-timeout exclusion |
| `tests/unit/engine`, `tests/integration/test_engine_cli.py` | 38 | match loop, CLI arguments, exit codes, full matches |
| `tests/determinism` | 13 | same seed twice, first divergent tick, `validate` / `compare` / `check-determinism` |
| `tests/unit/client`, `tests/integration/test_client_*.py` | 79 | history adapter, map rendering, replay controls, launcher, forced client close |
| `tests/e2e` | 10 | agents → engine process → history file → client, on 32/48/64 maps |

## Audit of the ten mandatory features

| # | Official must-have | Implementation | Executable evidence | Status |
| --- | --- | --- | --- | --- |
| 1 | Deterministic engine: two scripts and a seed, simulated until the budget or the step limit ends | `src/neon_armada/engine/{match,cli}.py`, `engine/core/mechanics.py` | `tests/integration/test_engine_cli.py`, `tests/unit/core/test_mechanics.py`, `tests/e2e/test_end_to_end.py::test_team_agent_plays_the_reference_agent_to_the_end` | PASS |
| 2 | Procedural map generator, symmetric, checked by traversal, controlled only by the seed | `engine/world/{generator,rng}.py` | `tests/unit/world/test_map_generator.py` | PASS |
| 3 | Engine–agent protocol over standard streams, starter kits in two languages | `contracts/agent-protocol.md`, `agents/python/`, `agents/cpp/` | `tests/integration/test_agent_protocol_smoke.py`, `tests/e2e/...::test_cpp_starter_agent_match_is_replayable_by_the_client` | PASS |
| 4 | Standardised, versioned history file format | `contracts/history-format.md`, `engine/history/writer.py`, `contracts/replay.py` | `tests/unit/contracts/test_contract_history_cli.py`, `tests/unit/contracts/test_replay.py` | PASS |
| 5 | Graphical client that loads the history and replays ships, map and resource collection | `src/neon_armada/client/` | `tests/integration/test_client_gui.py`, `tests/e2e/...::test_engine_history_is_valid_and_fully_replayable_by_the_client` | PASS |
| 6 | Replay controls: Pause, next step, x2 and x4, timeline | `client/replay.py`, `client/widgets/replay_controls.py` | `tests/unit/client/test_replay_controller.py`, `tests/integration/test_client_replay.py`, `tests/e2e/...::test_client_window_replays_an_engine_history_with_all_controls` | PASS |
| 7 | Full client flow: two local scripts, a seed, launch the engine, open the result automatically | `client/launcher.py`, `client/widgets/launch_dialog.py`, `client/main_window.py` | `tests/integration/test_client_launch.py::test_real_match_is_run_by_a_separate_process_and_opened` | PASS |
| 8 | Agent timeout without blocking the engine | `engine/agents/{runtime,limits}.py` | `tests/integration/test_agent_runtime.py`, `tests/integration/test_engine_cli.py::test_silent_agent_is_excluded_after_three_timeouts_and_match_completes`, `tests/e2e/...::test_match_with_faulty_agents_is_recorded_and_shown_by_the_client` | PASS |
| 9 | State fingerprints and a determinism checker comparing two runs | `contracts/fingerprint.py`, `contracts/replay.py`, engine `compare` / `check-determinism` | `tests/determinism/test_determinism.py`, `tests/e2e/...::test_same_seed_twice_gives_identical_fingerprints_and_compare_agrees` | PASS |
| 10a | Client–server integration test suite | `tests/integration/test_client_launch.py`, `tests/e2e/` | 22 tests, including `test_engine_survives_force_closing_the_client` | PASS |
| 10b | Project dashboard with tickets, Gantt chart and burndown chart | not in the repository | none: needs the team's real tracker data | **BLOCKED** |

Decoupling evidence (official demo item): `test_engine_survives_force_closing_the_client` starts
the client as its own process, lets it launch a match with deliberately slow agents, kills the
client mid-match, checks that the engine process is still alive and that no history exists yet,
then waits for the engine to finish and validates the 500-tick history it wrote. Verified on
Windows only.

## Product metrics (official targets)

Method: `scripts/collect_metrics.py`, team agent versus reference agent, seeds 1–10, each seed
played twice per map size (60 engine processes). Engine time is `timing.engine_ms` printed by
the engine: wall time of the match minus the time spent waiting for agent answers.

| Metric | Target | Measured | Status |
| --- | --- | --- | --- |
| Mean engine time, full 500-tick match, without agent time — 32x32 | under 2 s | mean 195 ms, max 256 ms (20 runs) | PASS |
| Same — 48x48 | under 2 s | mean 268 ms, max 356 ms (20 runs) | PASS |
| Same — 64x64 | under 2 s | mean 376 ms, max 510 ms (20 runs) | PASS |
| Determinism checker success rate (two runs, same fingerprints) | none stated | 30 of 30 seeds | PASS |
| Histories accepted by the client | none stated | 60 of 60 files | PASS |
| Integration blockers found | none stated | 0 open (see defects) | — |

Client frame rate. Method: `scripts/benchmark_gui.py`, 10 s of playback at x4 per map in the real
main window (1000x760), every repaint of the map timestamped. Playback repaints on a 16 ms
timer, so about 62 frames per second is the upper bound. Ten seconds at x4 cover the first
200 ticks of each match.

| Map | Qt platform | Average FPS | Minimum FPS over one-second windows | Slowest single frame | Target (minimum 30) |
| --- | --- | --- | --- | --- | --- |
| 32x32 | windows | 62.5 | 62 | 18.36 ms (54.5 FPS) | PASS |
| 48x48 | windows | 62.5 | 62 | 19.05 ms (52.5 FPS) | PASS |
| 64x64 | windows | 62.5 | 62 | 18.55 ms (53.9 FPS) | PASS |
| 32x32 | offscreen | 62.5 | 62 | 18.47 ms (54.2 FPS) | PASS |
| 48x48 | offscreen | 62.5 | 62 | 18.59 ms (53.8 FPS) | PASS |
| 64x64 | offscreen | 62.5 | 62 | 18.99 ms (52.6 FPS) | PASS |

## Game metrics (team agent as player 0 versus reference agent as player 1, seeds 1–10)

| Map | Wins team / reference / draw |
| --- | --- |
| 32x32 | 9 / 1 / 0 |
| 48x48 | 10 / 0 / 0 |
| 64x64 | 9 / 1 / 0 |

| Map | Player | Score mean (min..max) | Ships left (mean) | Invalid commands | Timeouts | Excluded | Agent time per match (mean) | Energy delivered by ticks 100, 200, 300, 400, 500 (mean) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32x32 | team | 3364 (2771..4020) | 3.0 | 0 | 0 | 0 | 146 ms | 1018, 1827, 2572, 3168, 3364 |
| 32x32 | reference | 2958 (2660..3182) | 1.0 | 0 | 0 | 0 | 43 ms | 536, 947, 1337, 1649, 1958 |
| 48x48 | team | 4058 (2503..5096) | 3.0 | 0 | 0 | 0 | 238 ms | 1255, 2230, 3077, 3790, 4058 |
| 48x48 | reference | 3210 (2422..3581) | 1.0 | 0 | 0 | 0 | 67 ms | 586, 1046, 1482, 1843, 2210 |
| 64x64 | team | 3883 (2594..4911) | 3.0 | 0 | 0 | 0 | 374 ms | 1128, 2085, 2902, 3623, 3883 |
| 64x64 | reference | 2988 (2597..3452) | 1.0 | 0 | 0 | 0 | 70 ms | 482, 882, 1283, 1652, 1988 |

Collisions in all 30 matches: 0. "Agent time" is the time the engine waited for that agent's
answers during a whole match. The matches were played with the team agent always as player 0;
the swapped sides were not measured in this run.

## Continuous integration

`.gitlab-ci.yml` now has a lint job and a test job that builds the C++ agent and runs the whole
suite with the Qt offscreen platform. **Not verified:** no pipeline was run. The repository's
only remote is on GitHub, where a `.gitlab-ci.yml` file is not executed; whether a GitLab
project exists for this repository could not be established from the repository.

Tracked dotfiles (`git ls-files`): `.clang-format`, `.editorconfig`, `.gitattributes`,
`.gitignore`, `.gitlab-ci.yml`, `.gitlab/` templates, `.github/skills/` (one file).

## Defects discovered

| ID | Description | Severity | Linked issue | Status |
| --- | --- | --- | --- | --- |
| D1 | `ruff format --check` failed in a fresh checkout on Windows: git converted line endings to CRLF while the formatter expects LF | Low | none (no tracker data in the repository) | Fixed in L11 by `.gitattributes` (`* text=auto eol=lf`) |
| D2 | `clang-format` 12 on the test machine cannot read the repository `.clang-format` (needs version 13 or newer), so C++ formatting was not checked by tool | Low | none | Open |

## Not verified

- Linux and macOS: no run. On macOS the agent memory limit is not applied (documented in the
  agent runtime); on Linux it relies on `RLIMIT_AS`.
- GitLab pipeline: not run (see above).
- Team metrics (tickets per sprint, velocity, burndown against the Gantt plan, time to close
  communication blockers): no data in the repository.

## Conclusion

Nine of the ten mandatory features, and the test-suite half of the tenth, have passing
executable evidence, and the three numeric product targets are met with margin on the test
machine. The delivery is **incomplete as a whole** because the project dashboard (tickets,
Gantt chart, burndown chart) required by must-have 10 does not exist in the repository and
can only be produced from the team's real work records.
