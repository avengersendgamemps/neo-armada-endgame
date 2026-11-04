# Agent Protocol Contract

**Status:** DRAFT — NOT APPROVED

## Purpose

Define the versioned standard-input/output protocol between the engine runtime
and each independently launched agent.

## Scope

This contract covers initialization, per-tick state delivery, command responses,
end-of-match signaling, validation, and error handling. It excludes engine
internals and reference-agent strategy.

## Components involved

- Engine agent runtime
- Python reference agent
- C++17 reference agent
- Any compatible external agent

## Information that must be specified

- Framing, encoding, message version, and one-message boundaries
- Initialization data, visible dynamic state, and command response shape
- Command-to-ship association, build requests, and ordering
- Timeout, memory-limit, malformed-response, and process-exit behavior
- End signal, diagnostics policy, and compatibility/version negotiation

The official MPS specification requires each agent to run as a separate process,
receive initialization and per-tick state through standard input, respond on
standard output, and be protected by time and memory limits. Invalid responses
must not stop the simulation; three consecutive timeouts exclude an agent.

## Open questions

- Concrete encoding and schema
- Visibility model and exact state projection
- Stream flushing and maximum message-size policy
- Timeout and memory-limit values
- Whether diagnostics use stderr and their retention policy

## Status

DRAFT — NOT APPROVED. Finalization belongs to E01.
