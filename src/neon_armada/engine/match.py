"""Headless match orchestration: map, agents, ticks, result.

The loop wires together the map generator, the pure mechanics and the agent
runtime in the official tick order. It contains no game rules of its own and
does not write files; it returns a :class:`MatchRecord` that the history
writer persists (``contracts/history-format.md``).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from neon_armada.contracts import protocol
from neon_armada.contracts.fingerprint import state_fingerprint
from neon_armada.contracts.models import (
    Exclusion,
    MatchConfig,
    MatchResult,
    MatchState,
    StaticMap,
)
from neon_armada.engine.agents.runtime import TickResponse
from neon_armada.engine.core.mechanics import (
    build_result,
    create_initial_state,
    end_reason,
    resolve_tick,
)
from neon_armada.engine.world.generator import (
    DEFAULT_PARAMS,
    GeneratorParams,
    generate_map,
)

Event = dict[str, Any]


class AgentPort(Protocol):
    """What the match loop needs from an agent (see ``AgentRuntime``)."""

    exclusion: Exclusion | None
    timeouts: int
    wait_seconds: float

    def start(self, init_message: dict[str, Any]) -> None: ...

    def finish_start(self) -> list[Event]: ...

    def request(self, tick_message: dict[str, Any]) -> None: ...

    def collect(self) -> TickResponse: ...

    def finish(self, end_message: dict[str, Any]) -> None: ...

    def abort(self) -> None: ...


@dataclass(frozen=True, slots=True)
class TickRecord:
    """Everything recorded for one tick."""

    tick: int
    events: tuple[Event, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class MatchTiming:
    """Wall-clock diagnostics. Non-deterministic; never part of the history."""

    total_ms: int
    agent_wait_ms: tuple[int, int]
    engine_ms: int


@dataclass(frozen=True, slots=True)
class MatchRecord:
    """Complete, immutable account of a finished match."""

    seed: int
    map_seed: int
    map_attempt: int
    config: MatchConfig
    agent_names: tuple[str, str]
    static_map: StaticMap
    initial_state: MatchState
    initial_fingerprint: str
    setup_events: tuple[Event, ...]
    ticks: tuple[TickRecord, ...]
    final_state: MatchState
    result: MatchResult
    timing: MatchTiming


def run_match(
    config: MatchConfig,
    seed: int,
    agents: Sequence[AgentPort],
    agent_names: tuple[str, str] = ("agent-a", "agent-b"),
    generator_params: GeneratorParams = DEFAULT_PARAMS,
    clock: Callable[[], float] = time.perf_counter,
) -> MatchRecord:
    """Play one complete match between two agents and return its record.

    Agent faults never raise: timeouts, malformed answers, crashes and
    exclusions are recorded as events and the simulation continues. Raises
    ``MapGenerationError`` if no valid map exists for the seed and
    ``ContractError`` for an invalid seed.
    """
    if len(agents) != 2:
        raise ValueError("a match needs exactly two agents")
    started = clock()
    generated = generate_map(seed, config.map_size, generator_params)
    static_map = generated.static_map
    initial_state = create_initial_state(config, static_map, generated.energy)
    state = initial_state
    ticks: list[TickRecord] = []
    collisions = 0

    try:
        for player, agent in enumerate(agents):
            agent.start(protocol.init_message(player, config, static_map))
        setup_events = tuple(
            event for agent in agents for event in agent.finish_start()
        )

        while True:
            # Phase 1: send the visible state to every agent.
            message = protocol.tick_message(state)
            for agent in agents:
                agent.request(message)
            # Phase 2: read the commands within each agent's time limit.
            responses = [agent.collect() for agent in agents]
            runtime_events = [event for r in responses for event in r.events]
            # Phases 3-8: validation, construction, movement, collisions,
            # mining and delivery are resolved by the pure mechanics.
            outcome = resolve_tick(
                state,
                static_map,
                [response.commands for response in responses],
                [response.malformed for response in responses],
            )
            state = outcome.state
            collisions += outcome.collisions
            # Phase 9: budgets are part of the state; fingerprint and events.
            ticks.append(
                TickRecord(
                    tick=state.tick,
                    events=tuple(runtime_events) + outcome.events,
                    fingerprint=state_fingerprint(state),
                )
            )
            reason = end_reason(state, config)
            if reason is not None:
                break

        result = build_result(
            state,
            reason,
            timeouts=(agents[0].timeouts, agents[1].timeouts),
            collisions=collisions,
            exclusions=(agents[0].exclusion, agents[1].exclusion),
        )
        finished = protocol.end_message("finished", result)
        for agent in agents:
            agent.finish(finished)
    except BaseException:
        for agent in agents:
            agent.abort()
        raise

    total = clock() - started
    waits = (agents[0].wait_seconds, agents[1].wait_seconds)
    return MatchRecord(
        seed=seed,
        map_seed=generated.map_seed,
        map_attempt=generated.attempt,
        config=config,
        agent_names=agent_names,
        static_map=static_map,
        initial_state=initial_state,
        initial_fingerprint=state_fingerprint(initial_state),
        setup_events=setup_events,
        ticks=tuple(ticks),
        final_state=state,
        result=result,
        timing=MatchTiming(
            total_ms=round(total * 1000),
            agent_wait_ms=(round(waits[0] * 1000), round(waits[1] * 1000)),
            engine_ms=round(max(0.0, total - sum(waits)) * 1000),
        ),
    )
