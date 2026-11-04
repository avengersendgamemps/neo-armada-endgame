# Engine CLI Contract

**Status:** DRAFT — NOT APPROVED

## Purpose

Define the command-line boundary used by the desktop client and development
tools to launch a complete engine match.

## Scope

This contract will specify invocation, inputs, outputs, exit behavior, and
diagnostics. It does not define the engine's internal API or graphical client.

## Components involved

- Desktop client
- Game-engine executable/module entry point
- Automation and integration tests

## Information that must be specified

- Command name, argument syntax, required agent launch specifications, and seed
- Optional configuration and output-history location
- Exit codes, stdout/stderr expectations, and diagnostic format
- File path behavior, overwrite policy, and platform considerations
- Contract version discovery and compatibility behavior

The official MPS specification requires the client to launch the engine locally,
provide agent scripts and a seed, and receive the completed match through a
history file. Client and engine have no persistent connection or direct function
calls.

## Open questions

- Exact executable or module invocation
- Argument names and configuration-file support
- Output-directory default and overwrite behavior
- Exit-code allocation and error-reporting format
- Handling of relative paths and spaces across supported platforms

## Status

DRAFT — NOT APPROVED. Finalization belongs to E01.
