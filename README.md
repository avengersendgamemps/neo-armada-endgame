# Neon Armada: Endgame

**Team:** Avengers Endgame  
**Status:** E00 — Project Foundation / initialization phase

Neon Armada: Endgame is a university software-engineering project based on the
MPS Armada assignment. It will deliver a deterministic, two-player strategy
simulation, externally executed reference agents, and a PySide6 desktop client
for loading and replaying match histories. No gameplay features are implemented
in this initialization phase.

## Technology stack

- Python 3.11+ and PySide6
- pytest and Ruff
- C++17, CMake, and clang-format
- GitLab CI and Git

## Repository layout

```text
src/neon_armada/     Python engine and desktop-client package boundaries
agents/              Python and C++ reference-agent workspaces
contracts/           Versioned integration-contract drafts
tests/               Unit, integration, determinism, and fixture directories
docs/                Architecture, planning, meeting, and report documents
coding-style/        Team Python and C++ standards
scripts/             Future development and validation helpers
```

## Development setup

Install Python 3.11+ and CMake. A C++17 compiler and clang-format are required
when implementing or formatting the C++ reference agent.

```bash
python -m pip install -e ".[dev]"
```

On systems where `python` is not available, use `python3` for the same commands.

## Quality checks

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
cmake -S agents/cpp -B build/cpp
```

## Contribution workflow

Use the issue and merge-request templates in `.gitlab/`. Work on the branch
selected by the coordinator, keep changes scoped to one task, read applicable
contracts before implementation, and submit changes through review. Branch names
follow `feature/MPS-XXX-description`, `bugfix/MPS-XXX-description`,
`test/MPS-XXX-description`, `docs/MPS-XXX-description`,
`chore/MPS-XXX-description`, or `ci/MPS-XXX-description`.

## Documentation

- Contracts: [`contracts/`](contracts/README.md)
- Architecture: [`docs/architecture/`](docs/architecture/overview.md)
- Planning: [`docs/planning/`](docs/planning/roadmap.md)
- Team standards: [`coding-style/`](coding-style/)
- Templates: [meetings](docs/meetings/template.md),
  [test reports](docs/reports/test-report-template.md), and
  [architecture decisions](docs/architecture/decisions/template.md)

The project remains in E00 until the coordinator approves this initialization.
