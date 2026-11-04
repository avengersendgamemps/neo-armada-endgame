# Integration Contracts

These documents are the shared boundaries among the engine, external agents, and
desktop client. They are intentionally **DRAFT — NOT APPROVED** during E00.
E01 will version and approve the concrete models, protocol messages, engine CLI,
and history format before dependent implementation starts.

The MPS Armada specification requires a deterministic engine, independently
executed agents communicating through standard input/output, and client–engine
communication through command line and a complete match-history file. The
documents here reserve those boundaries without defining unapproved schemas.

| Document | Boundary |
| --- | --- |
| [Game models](game-models.md) | Shared domain terminology and ownership |
| [Agent protocol](agent-protocol.md) | Engine-to-agent standard-stream exchange |
| [Engine CLI](engine-cli.md) | Client-to-engine process invocation |
| [History format](history-format.md) | Engine output consumed by the client |
