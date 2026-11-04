# Game Models Contract

**Status:** DRAFT — NOT APPROVED

## Purpose

Establish a versioned vocabulary and data-model boundary for game state handled
by the deterministic engine.

## Scope

This contract will describe domain representations needed by the engine,
external-agent protocol, and history format. It will not prescribe GUI objects
or implementation classes.

## Components involved

- Game engine
- Agent runtime and external agents
- Match-history writer and reader
- Desktop client

## Information that must be specified

- Model names, ownership, identifiers, and lifecycle
- Coordinates, map dimensions, static cells, bases, resources, and ships
- Player resources, move budgets, tick state, scores, and termination state
- Integer ranges, units, ordering, serialization ownership, and versioning
- Rules for validating and representing malformed or unavailable data

The official MPS specification requires deterministic, integer-only simulation
and identifies maps, bases, deposits, obstacles, ships, player energy, turns,
and state fingerprints as relevant concepts.

## Open questions

- Exact field names, types, and serialization representation
- Canonical coordinate origin and ordering
- Stable identifier allocation and ordering rules
- Exact configuration model and versioning policy
- State-fingerprint algorithm and canonical input ordering

## Status

DRAFT — NOT APPROVED. Finalization belongs to E01.
