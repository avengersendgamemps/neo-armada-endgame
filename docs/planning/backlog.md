# Backlog Format

Work is tracked through the hierarchy:

```text
Epic → Story → Task → Branch → Merge Request
```

Each task must record:

| Metadata | Requirement |
| --- | --- |
| ID | Stable issue identifier, such as `MPS-XXX` |
| Title | Short outcome-oriented title |
| Owner | Role identifier (`M1`–`M6`) |
| Priority | Agreed priority |
| Dependencies | Blocking issues, contracts, or decisions |
| Scope | Allowed modules and excluded work |
| Acceptance criteria | Observable completion conditions |
| Tests | Required validation and test location |
| Status | Proposed, ready, in progress, review, done, or blocked |

Branches follow the documented naming convention and merge requests link the
task.

## Current backlog

Taken from the repository on 2026-11-16. Issue identifiers, owners, priorities and
estimates are not recorded in the repository and must be filled in from the team's
tracker.

| ID | Title | Owner | Dependencies | Tests | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | L01 Contracts and domain models | TODO | E00 | `tests/unit/contracts` | Review |
| TODO | L02 Map generation and reachability | TODO | L01 | `tests/unit/world` | Review |
| TODO | L03 Pure game mechanics | TODO | L01 | `tests/unit/core` | Review |
| TODO | L04 Agent protocol and starter kits | TODO | L01 | `tests/unit/agents`, `tests/integration/test_agent_protocol_smoke.py` | Review |
| TODO | L05 Agent process runtime | TODO | L04 | `tests/integration/test_agent_runtime.py` | Review |
| TODO | L06 Headless engine and CLI | TODO | L02, L03, L05 | `tests/unit/engine`, `tests/integration/test_engine_cli.py` | Review |
| TODO | L07 History and determinism verifier | TODO | L06 | `tests/determinism`, `tests/unit/contracts/test_replay.py` | Review |
| TODO | L08 Desktop shell and map view | TODO | L01 | `tests/integration/test_client_gui.py` | Review |
| TODO | L09 Replay controls | TODO | L07, L08 | `tests/integration/test_client_replay.py` | Review |
| TODO | L10 Match launcher | TODO | L06, L07, L09 | `tests/integration/test_client_launch.py` | Review |
| TODO | L11 End-to-end tests, metrics, CI, report | TODO | L01–L10 | `tests/e2e`, `docs/reports/test-report-L11.md` | Review |
| TODO | L12 Documentation and demo script | TODO | L01–L11 | — | Review |
| TODO | Project dashboard (tickets, Gantt, burndown) | TODO | tracker data | — | Blocked |
| TODO | Communication plan and meeting minutes | TODO | team records | — | Blocked |
| TODO | Run CI pipeline; decide GitLab or GitHub | TODO | — | — | Proposed |
| TODO | Test on Linux or macOS | TODO | — | full suite | Proposed |
| TODO | Check C++ formatting with clang-format 13 or newer | TODO | — | — | Proposed |
| TODO | Animate ships into the collision cell during replay | TODO | L09 | — | Proposed |
