# Team Roles

Roles describe responsibility boundaries; they do not prevent review,
pairing, or shared ownership of quality.

| Role | Responsibility | Collaboration boundary |
| --- | --- | --- |
| M1 — Project Manager / Integration Lead | Coordinates planning, contracts, integration cadence, and release readiness. | Does not unilaterally change component contracts; obtains owner review. |
| M2 — Game Engine Developer | Owns deterministic turn execution, game-state rules, scoring, and termination. | Consumes approved models and reports required runtime/history data through contracts. |
| M3 — World & Economy Developer | Owns deterministic map generation, reachability, resources, and economy rules. | Supplies engine-facing behavior through approved domain models. |
| M4 — Agent & Protocol Developer | Owns external process runtime, protocol conformance, and reference-agent integration. | Does not embed agents in the engine or redefine domain rules. |
| M5 — GUI Developer | Owns PySide6 workflows, history loading, visualization, and playback controls. | Uses the CLI and history contracts rather than engine internals. |
| M6 — QA & DevOps Developer | Owns test strategy, CI, quality gates, determinism verification, and test reports. | Maintains automation without introducing gameplay behavior. |

## Members

> **TODO (team):** fill in who holds each role. The repository does not record the
> members' names. The assignment asks for teams of 7–8 people, while only six roles are
> defined above: add the missing role(s) or record which roles are shared.

| Role | Member |
| --- | --- |
| M1 | TODO |
| M2 | TODO |
| M3 | TODO |
| M4 | TODO |
| M5 | TODO |
| M6 | TODO |

## Roles and deliveries

Which role's area each delivery belongs to, following the responsibilities above. This
is the planned ownership by area, not a record of who did the work.

| Role | Deliveries in its area |
| --- | --- |
| M1 | L01 (contracts), L12 (documentation, demo) |
| M2 | L03 (mechanics), L06 (engine and CLI) |
| M3 | L02 (map generation) |
| M4 | L04 (protocol, starter kits, agents), L05 (agent runtime) |
| M5 | L08 (shell and map), L09 (replay), L10 (launcher) |
| M6 | L07 (determinism verifier), L11 (tests, metrics, CI, report) |

Cross-component changes require the relevant contract review before
implementation. M1 coordinates dependency resolution; M6 ensures integration
checks remain reproducible.
