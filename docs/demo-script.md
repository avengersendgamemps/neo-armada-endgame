# Demo script

About ten minutes. Run everything from the repository root in an activated virtual
environment (`python -m pip install -e ".[dev]"`). Commands are written for a POSIX
shell; in PowerShell replace the line-continuation `\` with a backtick or put the
command on one line.

## 0. Before the demo

```bash
cmake -S agents/cpp -B build/cpp && cmake --build build/cpp   # optional C++ agent
python -m pytest -q                                           # expect: all passed
```

## 1. Full flow from the client (must-have 7)

1. `python -m neon_armada.client`
2. **File > New match**. Agent A: `agents/python/team_agent.py`. Agent B:
   `agents/python/reference_agent.py`. Seed: `42`. Map size: `48`. **Run match**.
3. The status bar shows "Match running…"; the window stays usable.
4. When the engine finishes, the history opens by itself at tick 0.

Say: the client started `python -m neon_armada.engine run …` as a separate process and
then read the file it wrote; the command is recorded in
`histories/match-seed42.history.json.launch.json`.

## 2. Replay controls (must-haves 5 and 6)

1. **Play** (or Space): ships move smoothly between cells; deposits darken as they are
   mined; the panel shows base energy, ships, carried energy and move budget.
2. **Pause**.
3. **Next tick** (or N) a few times.
4. **x2**, then **x4**, then Play again.
5. Drag the **timeline** to the middle, then to the end: the winner and the reason are
   shown.

## 3. Map generation (must-have 2)

Start two more matches with seeds `1` and `2` (map size 32 and 64). Point out: the map is
the same when rotated by 180°, the bases are opposite each other, and a new seed gives a
new map.

## 4. Decoupling: force-close the client during a match (official demo item)

The reference match takes under a second, so use a slow agent to have time. Create
`slow_agent.py` anywhere:

```python
import json, sys, time
for raw in sys.stdin:
    message = json.loads(raw)
    if message["type"] == "init":
        reply = {"type": "ready", "protocol_version": 1}
    elif message["type"] == "end":
        break
    else:
        time.sleep(0.04)
        reply = {"type": "commands", "tick": message["tick"], "moves": [], "build": False}
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
```

1. `python -m neon_armada.client --agent-a slow_agent.py --agent-b slow_agent.py --seed 3 --output histories/decoupling.history.json`
2. While the status bar says "Match running…", kill the client: Task Manager > End task
   (Windows) or `kill -9` (Linux/macOS).
3. Show that `histories/decoupling.history.json` does not exist yet and that the engine
   process is still listed.
4. After about 20–40 seconds the file appears. Validate it:
   `python -m neon_armada.engine validate histories/decoupling.history.json`
   → `"valid": true, "ticks": 500`.

The same scenario runs automatically in
`tests/integration/test_client_launch.py::test_engine_survives_force_closing_the_client`.

## 5. Determinism (must-have 9)

```bash
python -m neon_armada.engine check-determinism \
    --agent-a agents/python/team_agent.py --agent-b agents/python/reference_agent.py --seed 42
```

Expect `"identical": true, "first_divergent_tick": null`. Then show a difference being
located:

```bash
python -m neon_armada.engine run --agent-a agents/python/team_agent.py \
    --agent-b agents/python/reference_agent.py --seed 42 --output histories/a.history.json
python -m neon_armada.engine run --agent-a agents/python/reference_agent.py \
    --agent-b agents/python/team_agent.py --seed 42 --output histories/b.history.json
python -m neon_armada.engine compare histories/a.history.json histories/b.history.json
```

Expect exit code 1 and the first tick that differs.

## 6. Faulty agent (must-have 8)

Run a match with an agent that never answers, for example the slow agent with
`time.sleep(5)`: the engine reports three timeouts, excludes the agent at tick 3 and
still finishes; the client shows "EXCLUDED: timeout at tick 3" for that player.

## 7. Measurements

Open [reports/test-report-L11.md](reports/test-report-L11.md): engine time per match,
frame rate, determinism rate, game metrics.

## 8. Project management

> **TODO (team):** present the real Gantt chart, the board and burndown chart, and how
> communication blockers were resolved. These are not in the repository.
