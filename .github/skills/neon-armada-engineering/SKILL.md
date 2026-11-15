---
name: neon-armada-engineering
description: Work on Neon Armada Endgame (MPS Armada) using the official assignment, approved versioned contracts, and the L01–L12 delivery plan. Applies to implementation, debugging, tests, reviews, integration, and documentation for the deterministic Python engine, PySide6 client, and Python/C++ agents.
---

# Neon Armada: Endgame — Repository Engineering Skill

**Team:** Avengers Endgame  
**Baseline:** E00 project foundation; do not assume any gameplay has been implemented  
**Primary implementation plan:** `Neon_Armada_Prompturi_Copilot_vFinal.md` (12 standalone delivery prompts, L01–L12)  
**Authoritative assignment:** https://ocw.cs.pub.ro/courses/mps/proiect

## 1. Authority, activation and scope

Use this skill for project work only. It is **shared policy**, not an instruction to autonomously implement every delivery. The selected L01–L12 prompt defines the *current task's* scope and acceptance criteria. The actual repository determines which files and features exist. Before claiming anything is approved or complete, inspect evidence.

Precedence when requirements disagree:

1. **Official MPS Armada assignment**, consulted live for the current task (or authoritative text provided by the user when unavailable).
2. **Versioned, approved project contracts**, only insofar as compatible with the assignment.
3. **Explicit human-approved delivery scope and coordinator milestone decisions**, including the selected L01–L12 prompt.
4. **Current repository implementation, tests, coding standards and planning records**, as evidence of actual state rather than authority to override requirements.
5. This shared skill and supplementary descriptions.

Do not silently reconcile contradictory requirements or make a team-level decision. Stop the affected portion, describe the exact conflict and ask for a documented decision. An approved contract cannot supersede an explicit official rule. Do not attribute team-selected numeric values or formats to the course assignment.

**E00 gate:** While E00 remains unapproved, work only on foundation, draft contracts, CI, templates and scaffolding. A delivery prompt (including L01) is not itself proof of coordinator approval to transition phases. Verify milestone approval in project coordination records or explicit instruction from the authorized coordinator before gameplay implementation. Do not arbitrarily block authorized L01–L12 work merely because the initial README still describes historical E00; report the discrepancy and request/verify status.

**No automatic delivery chain:** Complete only the explicitly requested delivery. Never continue to the next L number without a new human request, even if dependencies are satisfied.

## 2. Mandatory pre-implementation gates

Before **any changes** for L01–L12:

1. Run `git branch --show-current`. If branch is `main`, `master`, empty or detached, **STOP** and ask the human to select a non-main branch. Do not demand a specific branch name. Never create/switch branches, commit, merge, push, rewrite history, or change remotes on the user's behalf.
2. Inspect the actual repository tree, `README.md`, `pyproject.toml`, relevant `coding-style/` files, `contracts/`, appropriate implementation files, tests and planning status. Confirm stated prerequisites with concrete files/tests rather than assuming they exist.
3. Open and read the **live official assignment** at https://ocw.cs.pub.ro/courses/mps/proiect. Identify exact applicable requirements, numeric values, phase order, exceptions and relevant official section headings. **If inaccessible, STOP implementation and request the authoritative assignment text**; an AI summary, these prompts or memory is not sufficient. A human can supply a locally verified copy to continue.
4. Check approved contract versions, decision status and the delivery prompt against official text. **If essential details are missing, contradictory or undecided, stop the affected implementation and ask for clarification; never invent wire schemas, thresholds, tie-break rules or edge-case behavior.** Unblocked independent portions may proceed only if they remain within the approved delivery.
5. State the delivery ID, prerequisite status, relevant official requirements and any blockers. Then work only within that delivery's scope.

For reviews/explanations with no edits, inspect relevant evidence and explain findings; do not modify files. The branch gate applies before modifications, not before reading or answering questions.

**Course integrity:** Do not conceal any required AI-assistance disclosure. Do not create unnecessary AI configuration/docs. Never invent names, assignments, tests, GitLab events, meeting minutes, dates, approvals, metrics or historical evidence. Treat the **current README roster** as authoritative; do not overwrite it with an earlier six-person team assumption (L12 calls out seven members, but verify the current README rather than hardcoding names or count).

## 3. Project stack and repository map

| Concern | Stack / expected path |
| --- | --- |
| Python engine and desktop package boundaries | Python 3.11+, `src/neon_armada/` |
| Desktop GUI | PySide6, within `src/neon_armada/` |
| Independent agents | Python and C++17, `agents/`; CMake in `agents/cpp/` |
| Contract drafts and versions | `contracts/` |
| Tests and fixtures | `tests/` |
| Architecture, plans, meetings, reports | `docs/` |
| Python/C++ team standards | `coding-style/` |
| Utilities and CI | `scripts/`, `.gitlab-ci.yml`, `.gitlab/` |

Verify every path; this is a repository map, not proof of existence. Consult particularly:

- `contracts/game-models.md`, `contracts/agent-protocol.md`, `contracts/engine-cli.md`, `contracts/history-format.md`, `contracts/README.md` (L01 must reconcile these drafts).
- `docs/architecture/overview.md` and `docs/architecture/decisions/`.
- `docs/planning/roadmap.md`, `docs/planning/backlog.md`, `docs/planning/team-roles.md`.
- `docs/meetings/template.md`, `docs/reports/test-report-template.md`.
- The selected full L01–L12 prompt document, if available in the workspace; otherwise ask for its content when a delivery-specific requirement is needed.

Avoid introducing an alternate directory hierarchy or duplicated rules. Follow established code style and project configuration.

## 4. Delivery ownership and dependency graph

Use this matrix to identify the delivery's boundary. The **full selected delivery prompt** remains the task-specific checklist; the matrix is not a substitute.

| ID | Ownership | Required prerequisites | Explicit exclusions |
| --- | --- | --- | --- |
| **L01** | Versioned contracts, domain models, canonical examples, contract tests, freeze checklist | E00 scaffold + coordinator authorization | Gameplay, generator, agents, GUI |
| **L02** | Symmetric seeded map, BFS/DFS reachability, deterministic retry | Approved L01 map/config contracts | Mechanics, GUI |
| **L03** | Pure integer game state transitions, all tick mechanics and edge cases | Approved L01; L02 may be simulated by fixtures | Process runtime, full engine/CLI, GUI |
| **L04** | Agent protocol helpers, Python/C++ starter kits, functional reference agent, separate team-owned agent | Frozen L01 protocol | Process orchestration, game rules, GUI |
| **L05** | Agent subprocess lifecycle, limits, timeouts, exclusion, failures | L01 protocol + L04 agents | Full match orchestrator |
| **L06** | Headless engine CLI, full match orchestration, scoring, integration | L02 + L03 + L05 | GUI and final history persistence (L07) |
| **L07** | Versioned history, canonical fingerprints, history reader/reconstruction, verifier | L01 history contract + L06 engine | GUI controls |
| **L08** | PySide6 shell, 2D map and state presentation adapter | L01 state/map contracts | Replay controls and match launching |
| **L09** | Play/Pause/Step, ×2/×4, timeline seek and history-driven replay | L07 + L08 | Engine launch |
| **L10** | GUI agent/seed selection, isolated engine CLI launch, auto-open history | L06 + L07 + L09 | Direct engine imports, silent protocol changes |
| **L11** | Ten must-have audit, regression, E2E, performance, real CI/dashboard evidence | Integrated L01–L10 | Optional features, broad refactors |
| **L12** | Real documentation, SDD, evidence, clean-clone setup, milestone demo | Integrated/tested L01–L11 | Invented history, new optional features |

**Parallelism:** After L01 is approved, L02/L03/L04/L08 can progress separately within their own stated prerequisites. L05 follows L04; L06 follows L02/L03/L05; L07 follows L06; L09 follows L07/L08; L10 follows L06/L07/L09; L11 then L12. Do not infer that dependency completion equals acceptance without evidence.

## 5. Architectural invariants

```text
PySide6 client --CLI invocation--> independent headless engine
PySide6 client <--versioned history file-- engine
engine <--stdin/stdout protocol--> agent process A
engine <--stdin/stdout protocol--> agent process B
```

- Everything runs on the **same machine**. No internet server, hosted agents, user accounts or network match service.
- GUI must **not** import/call engine internals, share engine state, or maintain a persistent engine connection. Only CLI/process execution and history files bridge these components.
- Engine owns map generation, simulation, game rules, timeouts, scores, deterministic history and state fingerprints.
- Agents are independently executable programs; initial protocol message supplies static map; subsequent messages supply **dynamic** state only. Agents emit ship commands on stdout; diagnostics on stderr.
- A complete match history must be independently replayable **without** agents or rerunning game mechanics.
- L10 must verify that **force-closing the GUI while the match is running does not terminate the independent engine**, with reproducible evidence and OS caveats.
- No promise of hostile-code sandboxing. Agent resource limits are for trusted but faulty programs.

## 6. Contract-first rules (L01 is foundational)

Define and freeze **four related documents** before their consumers depend on them:

1. `contracts/game-models.md`: typed state/config/actions, map/coordinates, IDs, ownership, validations, integer arithmetic, stable ordering, team-resolved rule ambiguities.
2. `contracts/agent-protocol.md`: version, framing, initialization, per-tick observation, commands per ship, end/error, malformed/timeout handling, stdout/stderr behavior.
3. `contracts/engine-cli.md`: two agent executables/scripts, seed/config, output destination, usage, validation, errors and exit codes.
4. `contracts/history-format.md`: version, agents/seed/config, initial world, per-tick states/events/fingerprints, outcomes, invalid commands, failures and exclusions.

Maintain `contracts/README.md` with versions and **DRAFT / APPROVED / IMPLEMENTED** status. Contracts must contain canonical examples, valid/invalid fixtures, compatibility tests, exported interfaces and a freeze checklist. An unresolved mandatory item stays **UNAPPROVED**; report the blocker and do not declare contract freeze. Changing a cross-boundary schema requires a documented team-approved change, updated fixtures/tests and compatible consumers.

**Not specified numerically/by algorithm in the official page, unless later verified otherwise:** initial movement budget; agent timeout values; memory cap; initialization allowance; protocol wire schema and framing; derived-seed algorithm; final tie-break rule; canonical hash algorithm and any ambiguous build timing/phase behavior. Define these through a versioned, approved **team decision**, not guesses. Do not label team choices as official.

## 7. Official simulation invariants

These are a reference checklist from the assignment/prompt document; re-check the official site for the selected delivery and use approved contracts for the open details.

- Exactly **two** autonomous players, seeded symmetric **32–64**-side square map. Cells may be empty, deposits, obstacles or bases. Every deposit reachable from **both** bases; deterministically retry invalid maps using an approved derived seed.
- Start: **1,000 energy per base**, **one ship per player**; cargo limit **100**.
- Ship actions: north/south/east/west/stay. Move commands consume one movement-budget unit; stay consumes zero. Invalid obstacle/out-of-bounds/enemy-base moves are ignored and counted; reconcile budget accounting through approved contract.
- Building a ship costs **500** base energy; ship appears on the **following tick** if base free; contract must reconcile exact build scheduling with construction phase.
- Moving ships cannot mine. Stationary ship on deposit mines **ceil(cell's remaining energy / 10)**, capped by available cargo capacity. Use integer arithmetic.
- Deliver entire carried cargo on own base. Movement resolves **simultaneously** and fairly without player-first advantage.
- If two or more ships finish in the same cell, destroy all and add their carried cargo to that cell, **except own-base collision rule**; swapping two ship positions is **not** a collision. Formalize base exception in contract.
- Normal maximum **500 ticks**. Earlier finish only when **both movement budgets are exhausted AND no ship can still collect**.
- Score = final base-energy reserve. Tie-break: remaining ships, then carried energy, then approved fixed deterministic final rule.

**Exact tick sequence:**

1. Send agent observations.
2. Read agent commands within limits.
3. Validate and discard/record invalid commands.
4. Process construction.
5. Execute simultaneous movement.
6. Resolve collisions.
7. Mine for stationary ships.
8. Deposit cargo at own base.
9. Update budgets; compute fingerprint; write history events.

Do not reorder phases, resolve simultaneous moves sequentially, introduce floating-point-based simulation state, or silently invent an interpretation for an unspecified interaction.

## 8. Agent runtime, determinism and replay

**Agent faults:** On per-tick timeout, lose the tick and keep that agent's ships still; after **three consecutive timeouts**, exclude that agent and continue the match. Malformed responses and illegal commands must not crash the engine; ignore/count as specified and record exclusion reason/tick in history. Bound stdout/stderr and manage crashes, EOF, hung subprocesses and cleanup without blocking the match. Limits can be OS-specific; report limitations rather than claiming complete isolation.

**Determinism:** Same seed/config and deterministic agent decisions must yield the same integer simulation state and fingerprint tick by tick across supported platforms. Fix PRNG, seed derivation and iteration/serialization order in approved contracts. Do not hash timestamps, process identifiers, file paths or UI rendering data. The verifier reports the **first divergent tick**. Build canonical history fixtures, round-trip/corrupt/version tests and reconstruction checks for **every recorded tick**.

**GUI:** Consume contract-shaped histories or fixtures, not engine internal objects. Render 2D map, ships, bases, deposits, obstacles and changing resources. L08 creates shell/static rendering; L09 adds replay controls; L10 adds process launch. Keep the event loop responsive. Minimum playback features are **Play**, **Pause**, **next tick**, **×2**, **×4**, **seekable timeline**. Optional editor, campaigns and advanced effects are out of MVP scope.

## 9. Test, CI and measurable acceptance

Test specifically for the current delivery and regressions, not for unrelated future features:

- **L01:** canonical valid/invalid messages, versioning, cross-module interface fixtures, compatibility.
- **L02:** dimensions, symmetry, two-base resource reachability, deterministic retries, impossible configurations.
- **L03:** initial energy, build scheduling, legal/invalid moves, zero budget, simultaneous collisions, swaps, own bases, resource mining and end/tie-break cases.
- **L04–L05:** Python/C++ protocol smoke tests, stderr discipline, malformed/missing/oversize outputs, slow/silent/crashing agents, three-timeout exclusion and cleanup.
- **L06–L07:** full match CLI tests, fixed seeds, deterministic repeat histories, precise tick phases, history reconstruction, first differing fingerprint, corrupt/unsupported files.
- **L08–L10:** offscreen GUI smoke tests, renderer adapter, replay seeking/speeds, no UI blocking, engine survival after GUI forced closure.
- **L11:** end-to-end match with team-owned vs reference agent and evidence for each **of all ten official must-have features**.
- **L12:** clean-clone setup, installation/build, real project evidence and complete demo checklist.

Typical commands (verify paths/toolchains before running):

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
cmake -S agents/cpp -B build/cpp
cmake --build build/cpp
```

Use `python3` if needed, respect `.clang-format` and the team's Python/C++ styles. `cmake -S ...` merely configures; it does not prove the agent builds. Inspect `.gitlab-ci.yml` and actual GitLab CI state. If checking whether dotfiles are tracked, use `git ls-files`, not just directory/archive listings.

Record **actual measurements** with method/environment:

- Engine-only average full **500-tick** match duration **< 2 s**, excluding agent execution time.
- GUI average and minimum frame rate on multiple map sizes; target **>= 30 FPS**.
- Determinism success over seeds, history load rate, integration failures.
- Score distributions, resource collection, surviving ships, collisions, invalid commands, timeouts/exclusions, agent runtime.
- Real issues/MRs, sprint velocity, Gantt, burndown, meeting and blocker data.

Never claim unrun tests passed or that benchmark thresholds were reached without measurements. CI alone is not a substitute for an actual planning/dashboard artifact.

## 10. Git and development conduct

- The human selects the branch. Expected naming conventions: `feature/MPS-XXX-description`, `bugfix/MPS-XXX-description`, `test/MPS-XXX-description`, `docs/MPS-XXX-description`, `chore/MPS-XXX-description`, `ci/MPS-XXX-description`.
- Never run commands that change branch/history/remotes, commit, push or merge unless explicitly allowed by a different, overriding user workflow; the L01–L12 prompts themselves prohibit these operations.
- Keep edits as the smallest cohesive change for the selected delivery; no speculative abstractions, unrelated refactoring, silent contract changes, optional features or large formatting churn.
- Read local code/standards first; use explicit typing and small testable units. Pure engine mechanics must not depend on PySide6 or subprocesses.
- For bug fixes, reproduce, add a regression test when practical, fix the cause, rerun relevant checks and document compatibility impacts.
- Preserve any required university AI-use disclosures. Do not generate false historical documentation or ownership claims.

## 11. Required completion report / acceptance gate

Every L01–L12 delivery must end with a concise **requirements traceability matrix** covering its applicable official requirements:

| Official requirement + section | Implementation file/symbol | Test / actual execution evidence | Status |
| --- | --- | --- | --- |
| Precise requirement | Real location (or missing) | Exact command/result (or not run) | PASS / FAIL / BLOCKED / NOT APPLICABLE |

Then report:

1. **Delivery ID and prerequisite/milestone status**; source/specification gate confirmation and relevant sections.
2. **Files changed** and substantive behavior implemented; note decisions/contracts updated.
3. **Exact commands run and results**, including failures or unavailable tools; distinguish tested and inferred behavior.
4. **Open questions, OS/platform limitations, interface risks**, and deferred integration evidence.
5. **Delivery status: COMPLETE or INCOMPLETE.** If any applicable mandatory requirement is missing, unapproved, failing, or lacks necessary evidence, explicitly say **INCOMPLETE**; never claim acceptance. Do not proceed to another delivery.

For reviews without implementation, replace the implementation matrix with grounded findings and precise recommended next actions. When providing changed code in chat, show complete revised files rather than fragments if the user requests code content.

## 12. L12 documentation and final demonstration

Only once L01–L11 are genuinely integrated and tested:

- Complete README/Wiki with the **verified current roster and roles**, languages, external dependencies, development process, setup, engine CLI, agent builds and GUI use.
- Produce substantive `docs/architecture/SDD.md` (module boundaries, diagrams, data flows, versions, decisions and limitations).
- Update real roadmap/backlog/team roles, Gantt/Kanban/burndown, meeting minutes, test reports and evidence of work spread over the semester, **without inventing activity**.
- Demo selection of two agents + seed, match execution, history playback (Play/Pause/Step/×2/×4/seek), independent engine surviving forced GUI closure, deterministic same-seed fingerprints, and actual project-management records.
- Keep the product local and avoid optional features unless needed for a verified mandatory defect.

**Operating principle:** *Official specification first; approved contracts second; one authorized delivery at a time; prove behavior with real tests and traceability before calling it complete.*
