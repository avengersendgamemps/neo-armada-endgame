# Neon Armada: Endgame Development Instructions

## Architecture principles

- Keep the deterministic game engine independent from the PySide6 GUI.
- Keep agents as external processes; never import agent code into the engine.
- Follow approved, versioned contracts for the agent protocol, engine CLI, and
  history format.
- Preserve deterministic behavior and integer-only simulation requirements.
- Avoid unnecessary dependencies and prefer small, testable modules.

## Development rules

- Work on one task at a time and read the relevant contract before implementing.
- Do not implement unrelated functionality or silently alter a contract.
- Add focused tests for new functionality and run relevant quality checks.
- Follow `coding-style/CodingStyle-Python.txt` and
  `coding-style/CodingStyle-Cpp.txt`.
- Do not introduce optional features before mandatory requirements are complete.

## Git rules

- Work only on the branch selected by the user.
- Never create or switch branches unless explicitly instructed.
- Never merge, push, modify remotes, or rewrite shared history automatically.

## Task report

After each task, report the task ID, current branch, files modified, change
summary, tests executed, actual test results, known limitations, and dependencies
or blockers. Never claim a test passed unless it was executed.
