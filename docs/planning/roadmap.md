# Roadmap

Status on 2026-11-16, taken from the repository (`git log`). All twelve deliveries are
committed on stacked branches; none is merged into `main` yet and none has gone through
a merge request.

## Epics

| Epic | Name | Deliveries | Status |
| --- | --- | --- | --- |
| E00 | Project Foundation | — | Done (merged into `main` on 2026-11-04) |
| E01 | Contracts & Domain Models | L01 | Implemented, awaiting review |
| E02 | World Generation & Economy | L02, L03 | Implemented, awaiting review |
| E03 | Game Engine & Simulation | L06 | Implemented, awaiting review |
| E04 | Agent Execution & Protocol | L04, L05 | Implemented, awaiting review |
| E05 | History & Desktop Client | L07, L08, L09, L10 | Implemented, awaiting review |
| E06 | Quality, Integration & Delivery | L11, L12 | Implemented except the items marked blocked |

## Deliveries

| ID | Content | Branch | Commit | Committed |
| --- | --- | --- | --- | --- |
| L01 | Contracts and domain models | `feature/L01-contracts-domain-models` | `be97180` | 2026-11-16 |
| L02 | Map generation and reachability | `feature/L02-map-generation` | `8adaff6` | 2026-11-16 |
| L03 | Pure game mechanics | `feature/L03-game-mechanics` | `70cd3c6` | 2026-11-16 |
| L04 | Agent protocol and starter kits | `feature/L04-agent-protocol-starter-kits` | `6214428` | 2026-11-16 |
| L05 | Agent process runtime | `feature/L05-agent-process-runtime` | `e7c5dfa` | 2026-11-16 |
| L06 | Headless engine and CLI | `feature/L06-headless-engine` | `723b294` | 2026-11-16 |
| L07 | History and determinism verifier | `feature/L07-history-determinism` | `b21b896` | 2026-11-16 |
| L08 | Desktop shell and map view | `feature/L08-gui-shell-map` | `c8b9e39` | 2026-11-16 |
| L09 | Replay controls | `feature/L09-replay-controls` | `78e5d72` | 2026-11-16 |
| L10 | Match launcher | `feature/L10-match-launcher` | `85427c6` | 2026-11-16 |
| L11 | End-to-end tests, metrics, CI, test report | `feature/L11-quality-regression-performance` | `de68084` | 2026-11-16 |
| L12 | Documentation and demo script | `feature/L12-final-docs-demo` | this branch | 2026-11-16 |

Each branch is based on the previous one, so merging them in order (or merging only
`feature/L12-final-docs-demo`) brings everything into `main`. The branch names use the
delivery identifier because no issue identifiers (`MPS-XXX`) existed when they were
created.

## Open items

| Item | Owner | State |
| --- | --- | --- |
| Review and merge of the delivery branches | TODO (team) | Not started |
| Project dashboard: tickets, Gantt chart, burndown chart (must-have 10) | TODO (team) | Blocked: needs the team's real tracker data |
| Communication plan and meeting minutes | TODO (team) | Blocked: needs the team's real records |
| Team roster and roles in the README | TODO (team) | Open |
| Coordinator confirmation of the team rule decisions in `contracts/` | TODO (team) | Open |
| CI pipeline run (the CI file is for GitLab, the remote is on GitHub) | TODO (team) | Open |
| Test run on Linux or macOS | TODO (team) | Open |
