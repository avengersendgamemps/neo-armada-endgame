# Neon Armada: Endgame — 12 standalone Copilot implementation prompts (specification-aligned)

**Authoritative assignment:** https://ocw.cs.pub.ro/courses/mps/proiect (checked 2026-11-10; page shows last modified 2026-10-21).

Each prompt is independent: paste its entire code block into a fresh Copilot session on a manually selected non-main branch. No global AI configuration is required. Each prompt includes relevant **explicit official constraints**, plus a mandatory live check of the official page and existing versioned contracts. The prompt must stop if the authoritative page is unavailable; paste a locally verified copy of the official assignment into that session if necessary.

**Dependencies:** L01 first; after contract approval L02/L03/L04/L08 can run independently. L05 after L04; L06 after L02/L03/L05; L07 after L06; L09 after L07/L08; L10 after L06/L07/L09; L11 then L12. Branches are chosen by humans, not hard-coded.

**Requirements ownership:** L01 contracts and rule clarification; L02 map; L03 mechanics; L04 agent protocol/starter kits/reference + team agent; L05 limits; L06 engine; L07 history/hashes; L08 visualization; L09 replay; L10 launcher/decoupling; L11 mandatory cross-system verification and metrics; L12 documentation, dashboard and demonstration.

**Important distinctions:** The official page explicitly defines the ten must-have features, while some numerical limits (e.g. agent timeout, memory cap, initial movement budget), tie-break final rule, protocol wire schema and derived-seed algorithm must be specified by the team in versioned contracts. Team-owned agent is required by the objectives, even though the minimum reference-agent requirement is one. Dashboard/meeting evidence must come from real work, not be fabricated.

## L01 — Contracts and domain models

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L01: Contracts and domain models in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: E00 scaffold. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Concepte de bază; § Mecanici Joc; § Ciclul unui pas; § Agenți; § Contractele de comunicare; § Documentație.
- Define versioned engine-agent protocol (initial static map, dynamic per-tick observations, commands per ship, end/error), versioned history (header with version/seed/config/agent names, initial state, per-tick events/fingerprints, result), and CLI (two agents, seed, parameters, output, exit codes).
- Model integer-only deterministic simulation; square map side 32–64; symmetric map, bases, obstacles, deposits; initial 1000 base energy and one ship per player; cargo capacity 100; ship build cost 500; move budget; 500-tick maximum.
- Specify exact official tick order: observations; time-limited commands; validation; construction; simultaneous movement; collisions; stationary mining; base deposit; budgets, fingerprints and history.
- Contract collision semantics: all ships in same cell destroyed except own-base exception; swaps are not collisions; cargo goes to cell. Invalid moves (obstacle/outside/enemy base) ignored and counted.
- Explicitly document under-specified details (e.g. seed derivation, move budget initial value, command framing, timeout/memory numerical limits, tie-break final rule, build timing) as team decisions in versioned contracts; do not claim the official page supplies numbers it does not.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Define the smallest stable, versioned interfaces that let map, rules, agents, history and GUI teams work independently. Audit existing draft contracts and resolve specification-backed details before coding. Create typed domain representations for match configuration, players, ships, map cells/deposits, actions, match state and outcome; choose clear ownership and immutability boundaries. Specify coordinate system, IDs, serialization, validation, deterministic ordering, error conventions, agent stdin/stdout framing, engine CLI, history format and schema versioning. Supply canonical JSON examples and contract tests for valid/invalid messages. Keep engine/domain free of PySide6 and process-launch details. Do not implement gameplay, map generation, agents, replay or UI. When a specification decision is unresolved, document a concrete question and stop that portion rather than guessing. Finish with a contract freeze checklist listing exact exported symbols, schema versions and known open decisions. Explicitly finalize and validate the existing drafts in contracts/game-models.md, contracts/agent-protocol.md, contracts/engine-cli.md and contracts/history-format.md; keep contracts/README.md aligned. Provide executable fixtures and compatibility tests for all cross-module interfaces. If any official requirement cannot be resolved, keep the affected contract UNAPPROVED and report the blocker rather than declaring a freeze.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L02 — Map generation and accessibility

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L02: Map generation and accessibility in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01 approved map and configuration contracts. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Mecanici Joc; § Concepte de bază; must-have #2.
- Generate a square 32–64-cell map from integer seed; generate half and mirror/rotate for fair symmetric opportunities; cells may be empty, energy deposit, obstacle, or base.
- Every deposit must be reachable from BOTH bases by graph traversal; if invalid, retry deterministically using derived seed.
- Same seed/config and documented generator version must produce identical map; test symmetry, both-base reachability, base placement, obstacles, and retry.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Implement seeded map generation using the approved domain types. Follow exact official constraints for size, symmetry, base placement, obstacles and resource deposits. Check walkable connectivity and resource reachability from both bases using BFS/DFS; regenerate deterministically when invalid, with a bounded and explicit failure policy. Keep generation isolated from rendering and engine tick logic. Add tests for valid dimensions, mirrored/symmetric layout, valid bases, traversability, reachable deposits, identical seed/config yielding identical map, multiple representative seeds, and impossible configurations. Avoid hardcoding rules that conflict with the approved contracts. Do not implement movement, mining or GUI.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L03 — Pure game mechanics

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L03: Pure game mechanics in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01 contracts; L02 generator may be stubbed using fixtures. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Mecanici Joc; § Ciclul unui pas.
- Start each player with 1000 energy in base and one ship. Cargo max 100. Mining only when ship stays still on deposit: ceil(remaining cell energy / 10), capped by free cargo; moving ship does not mine.
- Deposit entire cargo upon reaching own base. Build costs 500 energy, new ship appears at base on next tick if base cell free, reconciled with official construction phase.
- Each movement command N/S/E/W consumes one movement-budget unit; staying consumes zero. Once exhausted, ships remain still. Invalid moves into obstacle, off map or enemy base are ignored and counted.
- After simultaneous movement, any 2+ ships in same cell are destroyed (own-base exception); their cargo is added to cell. Swapping two cells is NOT collision.
- Strict phase order: observations, commands, validation, construction, simultaneous movement, collisions, mining, deposit, budgets/fingerprint/history. Integer-only and no player ordering bias.
- End at 500 ticks or early ONLY when both movement budgets exhausted AND no ship can still mine. Score is base reserve; ties: surviving ship count, carried energy, then documented fixed rule.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Implement pure, independently testable state transitions for initial state, legal/illegal movement, simultaneous orders, movement budget, collision resolution, cargo destruction, mining, deposits at base, ship construction and economy, following the precise order and numbers in the official specification. Explicitly separate validation from transition logic. Use integer arithmetic and deterministic ordering. Define fixtures for edge cases: opposing moves into same cell, swap attempts, multiple ships, obstacle/base boundaries, insufficient energy, full cargo, depleted resource, no movement budget and invalid orders. Ensure neither player gains an artificial first-mover advantage. Use fixtures rather than coupling tests to the map generator. Do not implement external processes, full match loop, CLI or GUI. If tick-order or collision semantics are not specified in contracts, flag them before implementation.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L04 — Agent protocol and starter kits

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L04: Agent protocol and starter kits in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01 agent protocol frozen. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Agenți; § Contractele de comunicare; must-have #3.
- Agents are independent CLI processes communicating over stdin/stdout; initial message includes static map, each tick includes ONLY dynamic state (ships positions, cell energy, base reserve), agent replies with commands for each ship; end and errors defined.
- Deliver usable starter kits in at least TWO programming languages (project choice Python and C++17), plus at least ONE functioning reference agent for tests/demo and a team-owned playing agent. Do not confuse two-language starter kits with a requirement for two complete reference agents.
- Agents must respect approved framing, versions, flushing, build commands, IDs, and diagnostics channel; test protocol with engine-side fixtures.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Implement strict protocol serialization/parsing helpers and two usable agent starter kits, Python and C++17, following the approved stdin/stdout contract. Include one functional deterministic reference strategy that produces legal commands and a second compatible sample/starter in the other language; satisfy any stronger official requirement if applicable. Include CMake build instructions for C++, launch examples, protocol fixtures, malformed-message tests, and end-to-end request/response smoke tests for both languages when toolchains are available. Keep stdout protocol-only and send diagnostics to stderr. Do not implement process orchestration, sandbox limits, game rules or GUI. Do not invent protocol fields. Implement a separate team-owned strategy agent (not merely a renamed reference or starter template), with a simple deterministic resource-collection/return-to-base policy, obstacle avoidance and valid build decisions where permitted by the specification. Give it a distinct runnable entry point and tests proving it can participate in a full match once the engine is available. If full-match tests depend on L06, supply a contract-level smoke test now and explicitly list the deferred integration test for L11. Confirm the exact official requirements for starter kits, reference agents and team agents; implement any stronger requirement found in the official text.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L05 — External agent process runtime

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L05: External agent process runtime in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01 protocol; L04 starter agents. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Agenți; § Arhitectura sistemului; must-have #8.
- Engine starts each agent as independent process; initialization gets more generous timeout; per-tick time and memory limits must be enforced without blocking engine.
- Timed-out tick is lost and that agent's ships stay still; after THREE CONSECUTIVE timeouts exclude agent while match continues.
- Malformed responses/invalid commands never terminate match; ignore and count invalid commands. Record excluded agent, reason and exclusion tick in history.
- Trusted agents only: robust resource limits, NOT full hostile-code sandbox. Exact numeric time/memory values are contract decisions if unspecified by official page.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Build the engine-side subprocess runner for two independent external agents. Implement lifecycle, startup handshake if required, bounded stdin/stdout message exchange, per-turn timeouts, process termination/cleanup, invalid response handling, crash/EOF handling, and the officially required consecutive-timeout exclusion rule. Apply resource limits only where supported and documented; explain OS-specific limitations and avoid promising perfect sandboxing. Avoid deadlocks on stderr and unbounded output. Provide deterministic failure results that the engine can consume. Test with intentionally slow, crashing, silent, malformed and oversized-output dummy agents. Keep this layer separate from game state transitions and PySide6. Do not implement full match orchestration.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L06 — Complete headless simulation engine

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L06: Complete headless simulation engine in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L02 map; L03 mechanics; L05 agent runtime. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Mecanici Joc; § Ciclul unui pas; § Motorul; must-have #1.
- Headless CLI engine receives two agent scripts/executables, seed and parameters, generates symmetric accessible map, initializes each player with 1000 energy and one ship, executes up to 500 ticks with official early-termination condition.
- Every tick follows EXACT nine-phase order: send observations; read time-limited commands; validate; construct; simultaneous move; resolve collisions; stationary mine; deposit at own base; update budgets, fingerprint and history events.
- Official scoring: final base energy reserve; tie-break surviving ships then carried energy then documented fixed rule. Agent errors cannot block engine; deterministic integer-only simulation.
- Ensure clean hooks for L07 history, with final CLI output and errors compatible with approved contract.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Integrate existing map generation, pure mechanics and agent runtime into a complete headless match lifecycle. Implement configuration validation, seed handling, initialization, agent observation and simultaneous command collection, deterministic tick advancement, termination and official winner/tie-break rules. Provide the approved CLI for two agent executables/scripts and match parameters, clear exit codes, errors to stderr and machine-readable results where specified. Keep GUI completely decoupled. Add integration tests for full games with both reference agents, agent failures, fixed seeds, boundary conditions and official tick limits. Avoid duplicating mechanics in the orchestrator. Leave history persistence to L07 except for agreed event/state hooks.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L07 — History and deterministic verification

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L07: History and deterministic verification in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01 history contract; L06 engine. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Concepte de bază; § Contractele de comunicare; must-have #4 and #9.
- Versioned standardized history must include format version, seed, parameters, agent names, initial state, per-tick events, per-tick state fingerprints and final result; record invalid commands, timeouts and agent exclusion with reason/tick.
- History alone must be sufficient to reconstruct every frame without rerunning agents; compare reconstructed states against fingerprints.
- Determinism verifier runs or compares two identical-seed/identical-agent matches and reports FIRST differing tick. Hash only canonical integer simulation state, not timestamps/paths.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Implement versioned match history persistence from engine hooks: metadata, configuration/seed, initial state, per-tick changes or snapshots as specified, agent outcomes, final result and per-tick state fingerprints. Define canonical serialization and stable hashing of simulation-relevant state. Implement a reader/validator and a command or test helper to compare two histories and report the first divergent tick. Ensure a complete match can be reconstructed from the recorded initial state and tick data without re-running the agents or simulation rules; provide a reconstruction test comparing every reconstructed state with the recorded canonical fingerprints. Test round trips, truncated/corrupt/unsupported-version files, deterministic repeat runs with controlled agents and identical seeds, and changes that should alter fingerprints. Do not accidentally hash timestamps, paths or other nondeterministic metadata. Do not build GUI replay controls.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L08 — PySide6 desktop shell and map visualization

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L08: PySide6 desktop shell and map visualization in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01 map/state contracts. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Clientul; § Arhitectura sistemului; must-have #5.
- GUI reads approved standardized history and graphically shows 2D map, ships, bases, obstacles, energy deposits and collection changes; simple graphics are sufficient.
- GUI must NOT call engine functions or share engine memory. Client/server communication exclusively CLI and files; local same-machine architecture.
- Use contract-shaped fixture data until L07 reader is ready; do not implement optional editor, campaigns, advanced effects.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Create a responsive PySide6 desktop application shell with a 2D map renderer for cells, obstacles, resource deposits, bases and ships, plus essential tick/player/score information. Use a clean presentation adapter that consumes approved state/history DTOs; while the engine/history are unfinished, use clearly isolated contract-conforming fixtures rather than inventing alternate formats. Ensure the GUI never imports engine internals or runs game rules. Add smoke tests for application startup and renderer/state adaptation, including headless/offscreen CI support when practical. Handle empty/invalid input gracefully. Do not implement match launching or playback controls beyond a static preview.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L09 — History replay controls

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L09: History replay controls in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L07 history reader; L08 GUI. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Clientul; must-have #5 and #6.
- Implement Play, Pause, next-tick step, x2 and x4 playback speed and seekable timeline over history states.
- Reconstruct visible ship/map/resource-collection state for arbitrary tick without invoking game engine or agents; handle beginning/end/invalid history.
- GUI performance target minimum 30 FPS (measure and report; do not assert without measurement).
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Implement replay controller and UI controls for play/pause, single-tick step, seeking via timeline and selectable playback speed. Load histories using the versioned reader; update the map and statistics from recorded states/events, never by re-running game mechanics. Support seeking to first/last tick, empty/short histories, pause during seek, speed changes and corrupted files with user-visible errors. Keep timing independent from simulation state. Add controller tests and GUI smoke tests; ensure replay does not block the event loop. Do not add match launching or engine process calls.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L10 — Launch matches from desktop

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L10: Launch matches from desktop in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L06 CLI; L07 history; L09 replay. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Arhitectura sistemului; § Clientul; must-have #7; milestone demo.
- Client selects TWO local agent scripts/executables and integer seed, launches engine as SEPARATE OS PROCESS via approved CLI, waits for result and opens resulting history automatically.
- No direct function calls, persistent link or shared memory between GUI and engine; communication through command line and history file only.
- Verify force-closing GUI during an ongoing engine run does NOT terminate independent engine; implement process lifetime appropriately and demonstrate with a real test.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Add GUI workflow to select two agent programs/scripts, configure allowed match parameters including seed, validate inputs, launch the engine as a separate child process via the approved CLI, show progress/errors without freezing the UI, and load the produced history into replay after completion. Safely handle missing executables, invalid paths, crashes, timeouts/cancellation where specified and nonzero exit codes. Avoid shell-string execution and direct imports of engine internals. Explicitly verify process isolation: closing or force-killing the GUI during an active match must not terminate the independent engine when the official requirement expects it to continue. Choose process ownership and lifecycle accordingly; provide a reproducible integration test or demo script and record OS-specific caveats. Add tests with fake engine process and a real end-to-end smoke test when dependencies exist. Do not change CLI or history contracts silently.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L11 — Quality, regression and performance

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L11: Quality, regression and performance in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01-L10 integrated. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Statistici Măsurabile; § Livrabile; § Limitări; must-have #1–#10.
- End-to-end tests for engine, agents, history, GUI/CLI boundary, replay, timeout, malformed commands, 3 consecutive timeouts, independent engine after forced GUI close and deterministic hashes.
- Measure simulation-only mean runtime for full 500-tick match, excluding agent time (target <2 seconds); GUI average and minimum FPS for varied map sizes (target >=30 FPS); deterministic verifier success across seeds; history load success/integration crashes.
- Capture game metrics: final scores/distributions, energy over time, remaining ships, collisions, invalid commands, timeouts/exclusions and agent execution time. Record actual measured data and environment.
- Verify GitLab CI tests/lint and C++ build, and actual project dashboard issues/Gantt/burndown evidence; CI alone does not satisfy dashboard requirement.
- Audit all TEN must-have features individually with implementation and executable test evidence; do not mark blocked features complete.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Audit mandatory requirements against implemented behavior. Add high-value end-to-end tests for engine+agents+history+GUI adapter, failure handling, contract compatibility, deterministic replay and multiple seeds. Include a real match using the team-owned agent against the reference agent, history reconstruction checks, and a GUI-force-close test proving the engine continues independently when required by the official specification. Measure simulation-only runtime separately from agent runtime, and GUI responsiveness/frame rate where specified; report environment, methodology and measured numbers rather than asserting targets. Check whether .gitlab-ci.yml exists and runs in the actual GitLab project; if missing, add it. Ensure CI covers Python tests/lint and C++ build/tests when available, with clear platform limitations. Verify tracked dotfiles using git ls-files, not only an archive listing. Fix only defects directly blocking mandatory behavior; record larger refactors as issues. Produce reproducible test reports and a requirements-to-tests matrix that covers ALL official mandatory features and their exact performance thresholds; explicitly mark any feature without passing evidence as incomplete. Do not introduce optional features.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```

## L12 — Final delivery, documentation and demonstration

```text
Before implementing this delivery, load and follow the neon-armada-engineering skill from .github/skills/neon-armada-engineering/SKILL.md. Apply its engineering rules alongside this delivery's requirements and the official MPS specification.
You are implementing delivery L12: Final delivery, documentation and demonstration in the existing Neon Armada: Endgame repository.
Before any changes, run `git branch --show-current` and verify the current branch is neither `main` nor `master` and is not detached HEAD. If the check fails, STOP and ask the user to switch branches manually. Do not require a specific branch name.
Prerequisites: L01-L11 integrated and tested. Verify these exist before implementing.

WORKFLOW AND SAFETY
Before changing code, inspect the current repository structure, README, pyproject.toml, coding-style files, contracts, and relevant tests. MANDATORY SPECIFICATION GATE — BEFORE IMPLEMENTATION: Open and read the official Armada assignment at https://ocw.cs.pub.ro/courses/mps/proiect. Identify the exact mandatory requirements relevant to THIS delivery, including numeric limits, edge cases, ordering and expected behavior; list them briefly with the corresponding specification sections. Compare each against existing contracts, code and this prompt. The official assignment has priority; approved contracts are binding only when compatible with it. If the official page cannot be accessed, STOP and request the authoritative assignment text from the user: do not implement from assumptions, remembered rules or local summaries alone. If requirements are ambiguous, missing, or contradictory, STOP the affected implementation and ask for clarification before writing code; never silently invent or override game rules. Confirm the specification gate and any blockers in your completion report. Work on the currently checked-out branch only: do not create/switch branches, commit, merge, push, change remotes, or rewrite history. Do not introduce unnecessary AI-assistant configuration files or AI-specific documentation. Do not erase or conceal any disclosure required by course policy. Preserve any disclosure obligations. Make the smallest cohesive changes for this delivery, write tests, run applicable checks, and report exact commands/results, changed files, limitations, and prerequisites. Treat the current README team roster as authoritative; never reduce it to an earlier six-person plan. Do not fabricate GitLab activity, ownership, dates, or tests. Do not claim unrun checks passed. Stop when this delivery is complete.

OFFICIAL REQUIREMENTS — EXPLICIT DELIVERY CHECKLIST
Source: https://ocw.cs.pub.ro/courses/mps/proiect
Relevant official sections: § Livrabile; § Documentație; § Statistici Măsurabile; milestone demo.
- README/Wiki must contain ACTUAL seven team members/roles, languages, external solutions/dependencies, chosen development methodology, installation and usage.
- Versioned protocol/history/CLI contracts and documented extra rules; substantive SDD; real team/task planning (Gantt, Kanban/Scrum board, timeline, burndown), communication plan and real meeting minutes (decisions/actions/owners/dates), test reports.
- Provide evidence of continuous work and major changes at most two weeks apart, genuine issues/MRs, estimates vs actual and role responsibilities; NEVER fabricate history, metrics or contributions.
- Demo: choose two local agents and seed; run match; play/pause/step/x2/x4/timeline; prove CLI/file decoupling by force-closing GUI while engine continues; compare same-seed fingerprints; present Gantt and communication blockers.
- Local standalone application only; no network server, accounts, agent hosting or optional code editor/campaign/advanced effects.
For each bullet, cite the corresponding official section in the completion matrix. The above is a verified implementation checklist, not a replacement for the official page. Where the page leaves a value or behavior undefined, record a documented deterministic team decision in the approved contract before implementation; do not falsely attribute it to the assignment.

DELIVERY SCOPE
Prepare final user-facing README with setup, supported OS/toolchain versions, engine CLI, agent starter-kit build/run, GUI use, match launch and replay. Create or complete docs/architecture/SDD.md as a substantive Software Design Document describing architecture, module boundaries, diagrams, data flows, contract versions, design decisions, limitations and reproducible testing. Update docs/planning/roadmap.md and docs/planning/backlog.md to reflect actual deliveries and current status, not obsolete E00-only planning. Preserve the seven-person team roster already in README; align docs/planning/team-roles.md with actual membership and verified responsibilities, without inventing names or assignments. Document the real development methodology, actual external dependencies and any university-required tooling or AI-use disclosures in README/Wiki as applicable. Assemble project-management evidence from actual GitLab issues/MRs/meetings, estimates, Kanban/Gantt/burndown and test reports; do not fabricate contributions, dates, metrics or meeting records. Provide a concise demo script covering map generation, reference agent versus team-owned agent, full match, history, replay, determinism, and force-closing the GUI without stopping the independent engine where required. Verify clean-clone setup, lint/tests/build and packaging as applicable. Do not alter game rules or add optional features unless required to repair a confirmed defect.

ACCEPTANCE GATE
Create a concise requirements traceability table for THIS delivery: official requirement / implementation location / test evidence / status (PASS, FAIL, BLOCKED, NOT APPLICABLE). Verify every applicable mandatory requirement against the official text and approved contracts. Distinguish actual test output from unverified assumptions. If a mandatory item is missing or failing, explicitly report the delivery as INCOMPLETE; do not silently mark it done. Do not proceed to the next delivery.
```
