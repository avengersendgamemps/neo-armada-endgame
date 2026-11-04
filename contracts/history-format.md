# Match History Format Contract

**Status:** DRAFT — NOT APPROVED

## Purpose

Define a versioned, complete match-history artifact produced by the engine and
consumed by the desktop client for playback and verification.

## Scope

This contract covers persisted match data and compatibility. It does not define
the renderer, user controls, or internal runtime data structures.

## Components involved

- Game engine
- Match-history writer
- Desktop client and playback controls
- Determinism tests and tooling

## Information that must be specified

- File encoding, top-level version, and validation rules
- Match metadata, seed, parameters, and agent-identification data
- Initial state, ordered per-tick events/states, and final result
- State fingerprints and behavior for invalid commands, timeouts, and exclusions
- Ordering, extensibility, backward compatibility, and corruption handling

The official MPS specification requires the history to contain the header,
initial state, each tick's events, state fingerprints, and final result so the
match can be reconstructed and determinism can be checked.

## Open questions

- Concrete serialization format and schema
- Snapshot-versus-event balance and replay guarantees
- Fingerprint algorithm and canonicalization
- Compression, file-size limits, and forward-compatibility policy
- Validation and recovery behavior for incomplete files

## Status

DRAFT — NOT APPROVED. Finalization belongs to E01.
