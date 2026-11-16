"""Starter template for a Python agent.

Copy this file, rename it and replace the body of :func:`decide`. The template
is a complete, valid agent: every ship stays in place (and therefore mines if
it happens to stand on a deposit).

Run by the engine as: ``python -u starter_agent.py``.
"""

from __future__ import annotations

from neon_agent_kit import STAY, Commands, Game, TickState, log, run


def decide(game: Game, state: TickState) -> Commands:
    """Return the commands for this tick."""
    commands = Commands()
    if state.tick == 1:
        log(f"starter agent: player {game.player_id}, base at {game.my_base}")
    for ship in state.my_ships:
        # Ideas: game.step_towards(ship.pos, target) gives the next move on a
        # shortest path; state.energy maps (x, y) to the energy of a cell;
        # commands.request_build() orders a new ship for 500 energy.
        commands.move(ship.id, STAY)
    return commands


if __name__ == "__main__":
    raise SystemExit(run(decide))
