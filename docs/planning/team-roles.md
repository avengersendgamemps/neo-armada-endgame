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

Cross-component changes require the relevant contract review before
implementation. M1 coordinates dependency resolution; M6 ensures integration
checks remain reproducible.
