# Agents and starter kits

Agents are independent command-line programs. They follow
[`contracts/agent-protocol.md`](../contracts/agent-protocol.md) (version 1):
JSON Lines on stdin/stdout, diagnostics on stderr. They never import the
engine.

| File | Language | Purpose |
| --- | --- | --- |
| `python/neon_agent_kit.py` | Python | Starter kit: protocol loop, state views, shortest-path helpers |
| `python/starter_agent.py` | Python | Template to copy; every ship stays in place |
| `python/reference_agent.py` | Python | Reference agent for tests and demos (greedy collector, one ship) |
| `python/team_agent.py` | Python | Team-owned agent "Endgame" (fleet building, target scoring, enemy avoidance) |
| `cpp/include/neon_agent_kit.hpp` | C++17 | Header-only starter kit (no external libraries) |
| `cpp/src/starter_agent.cpp` | C++17 | Functional starter agent built on the kit |

## Python

Requires Python 3.11+ and nothing else. The engine starts `.py` agents as
`python -u <file>`. To try one by hand, start it and paste protocol lines:

```bash
python -u agents/python/reference_agent.py
```

To write your own agent, copy `starter_agent.py` next to `neon_agent_kit.py`
and change `decide(game, state)`.

## C++17

Requires CMake 3.20+ and a C++17 compiler (GCC, Clang or MSVC).

```bash
cmake -S agents/cpp -B build/cpp
cmake --build build/cpp
```

The executable is written to `build/cpp/bin/neon_starter_agent` (with `.exe`
on Windows) for every generator. Pass that path to the engine as an agent.
To write your own agent, copy `src/starter_agent.cpp`, add an
`add_executable` entry in `CMakeLists.txt` and change `decide`.

## Rules every agent must follow

- Answer `init` with `ready`, and every `tick` with one `commands` line whose
  `tick` equals the tick received; flush stdout after each line.
- Print nothing else on stdout. Use stderr for logs.
- Exit after `end` or when stdin is closed.
- Stay within the time and memory limits from the `init` message's `config`.
