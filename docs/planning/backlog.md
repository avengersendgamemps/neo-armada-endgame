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
task. This document defines the format only; a complete backlog will be planned
after E00 approval.
