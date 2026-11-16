"""Measure the product and game metrics of the official assignment.

Usage::

    python scripts/collect_metrics.py [--seeds 1-10] [--map-sizes 32,48,64]
        [--agent-a agents/python/team_agent.py]
        [--agent-b agents/python/reference_agent.py]
        [--output-dir metrics-out]

For every map size and seed the engine is run **twice** through its command
line (a separate process each time). From these runs the script reports:

* engine time of a match without agent time (``timing.engine_ms`` printed by
  the engine: wall time minus the time spent waiting for agents);
* determinism: share of seeds whose two runs have identical fingerprints
  (engine ``compare`` command);
* history acceptance: share of histories the client adapter loads and
  reconstructs completely;
* game metrics: scores, ships left, collisions, invalid commands, timeouts,
  exclusions, time spent waiting for each agent, energy delivered over time.

Results are written to ``OUTPUT_DIR/metrics.json`` (everything) and
``OUTPUT_DIR/metrics.md`` (summary tables). Nothing is asserted: the numbers
are whatever was measured on this machine.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

from neon_armada.client.presentation import MatchPresentation
from neon_armada.contracts.cli import ENGINE_MODULE
from neon_armada.contracts.history import HistoryError
from neon_armada.contracts.replay import load_history

REPO_ROOT = Path(__file__).resolve().parent.parent
ENERGY_SAMPLE_TICKS = (100, 200, 300, 400, 500)


def engine(*arguments: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE, *arguments],
        capture_output=True,
        text=True,
        timeout=600,
    )
    lines = completed.stdout.splitlines()
    return completed.returncode, json.loads(lines[-1]) if lines else {}


def parse_seeds(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        if "-" in part:
            low, high = part.split("-", 1)
            seeds.extend(range(int(low), int(high) + 1))
        else:
            seeds.append(int(part))
    return seeds


def delivered_over_time(path: Path) -> list[list[int]]:
    """Cumulative energy delivered to each base at the sample ticks."""
    history = load_history(path)
    owner = {ship.id: ship.owner for ship in history.initial_state.ships}
    totals = [0, 0]
    samples = []
    for entry in history.ticks:
        for event in entry.events:
            if event["type"] == "ship_spawned":
                owner[event["ship"]] = event["player"]
            elif event["type"] == "delivered":
                totals[owner[event["ship"]]] += event["amount"]
        if entry.tick in ENERGY_SAMPLE_TICKS:
            samples.append(list(totals))
    return samples


def accepted_by_client(path: Path) -> bool:
    try:
        presentation = MatchPresentation.from_file(path)
        presentation.frame(presentation.last_tick)
    except (HistoryError, IndexError):
        return False
    return True


def measure(agent_a: Path, agent_b: Path, size: int, seed: int, directory: Path):
    """Play one seed twice; return the row of measurements."""
    paths, payloads = [], []
    for run in ("a", "b"):
        path = directory / f"size{size}-seed{seed}-{run}.history.json"
        code, payload = engine(
            "run",
            "--agent-a",
            str(agent_a),
            "--agent-b",
            str(agent_b),
            "--seed",
            str(seed),
            "--map-size",
            str(size),
            "--output",
            str(path),
        )
        if code != 0:
            return {"map_size": size, "seed": seed, "error": payload}
        paths.append(path)
        payloads.append(payload)
    _, comparison = engine("compare", str(paths[0]), str(paths[1]))
    _, validation = engine("validate", str(paths[0]))
    result = payloads[0]["result"]
    return {
        "map_size": size,
        "seed": seed,
        "ticks_played": result["ticks_played"],
        "end_reason": result["end_reason"],
        "winner": result["winner"],
        "scores": result["scores"],
        "ships_remaining": result["ships_remaining"],
        "collisions": result["collisions"],
        "invalid_commands": result["invalid_commands"],
        "timeouts": result["timeouts"],
        "exclusions": result["exclusions"],
        "engine_ms": [payload["timing"]["engine_ms"] for payload in payloads],
        "total_ms": [payload["timing"]["total_ms"] for payload in payloads],
        "agent_wait_ms": [payload["timing"]["agent_wait_ms"] for payload in payloads],
        "deterministic": comparison.get("identical") is True,
        "first_divergent_tick": comparison.get("first_divergent_tick"),
        "history_valid": validation.get("valid") is True,
        "accepted_by_client": all(accepted_by_client(path) for path in paths),
        "delivered_over_time": delivered_over_time(paths[0]),
    }


def mean(values) -> float:
    values = list(values)
    return round(statistics.fmean(values), 1) if values else 0.0


def summarise(rows: list[dict], names: tuple[str, str]) -> str:
    """Return the Markdown summary of the measured rows."""
    good = [row for row in rows if "error" not in row]
    lines = [
        "| Map | Seeds | Engine ms mean / max (500-tick matches) | Deterministic |"
        " Accepted by client | Wins A / B / draw |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for size in sorted({row["map_size"] for row in good}):
        group = [row for row in good if row["map_size"] == size]
        full = [
            ms for row in group if row["ticks_played"] == 500 for ms in row["engine_ms"]
        ]
        wins = [sum(1 for row in group if row["winner"] == w) for w in (0, 1, None)]
        lines.append(
            f"| {size}x{size} | {len(group)} | {mean(full)} / {max(full, default=0)}"
            f" ({len(full)} runs) |"
            f" {sum(row['deterministic'] for row in group)}/{len(group)} |"
            f" {sum(row['accepted_by_client'] for row in group)}/{len(group)} |"
            f" {wins[0]} / {wins[1]} / {wins[2]} |"
        )
    sample_ticks = ", ".join(map(str, ENERGY_SAMPLE_TICKS))
    lines += [
        "",
        "| Map | Player | Score mean (min..max) | Ships left mean |"
        " Invalid commands | Timeouts | Exclusions | Agent wait ms mean |"
        f" Delivered energy at ticks {sample_ticks} (mean) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for size in sorted({row["map_size"] for row in good}):
        group = [row for row in good if row["map_size"] == size]
        for player in (0, 1):
            scores = [row["scores"][player] for row in group]
            waits = [w[player] for row in group for w in row["agent_wait_ms"]]
            curve = [
                mean(row["delivered_over_time"][index][player] for row in group)
                for index in range(len(ENERGY_SAMPLE_TICKS))
                if all(len(row["delivered_over_time"]) > index for row in group)
            ]
            lines.append(
                f"| {size}x{size} | {player}: {names[player]} |"
                f" {mean(scores)} ({min(scores)}..{max(scores)}) |"
                f" {mean(row['ships_remaining'][player] for row in group)} |"
                f" {sum(row['invalid_commands'][player] for row in group)} |"
                f" {sum(row['timeouts'][player] for row in group)} |"
                f" {sum(row['exclusions'][player] is not None for row in group)} |"
                f" {mean(waits)} | {', '.join(str(value) for value in curve)} |"
            )
    collisions = sum(row["collisions"] for row in good)
    lines += ["", f"Collisions in all matches: {collisions}."]
    failed = len(rows) - len(good)
    if failed:
        lines.append(f"Matches that could not be run: {failed}.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--map-sizes", default="32,48,64")
    parser.add_argument(
        "--agent-a", type=Path, default=REPO_ROOT / "agents/python/team_agent.py"
    )
    parser.add_argument(
        "--agent-b", type=Path, default=REPO_ROOT / "agents/python/reference_agent.py"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("metrics-out"))
    arguments = parser.parse_args()
    seeds = parse_seeds(arguments.seeds)
    sizes = [int(size) for size in arguments.map_sizes.split(",")]
    histories = arguments.output_dir / "histories"
    histories.mkdir(parents=True, exist_ok=True)

    rows = []
    for size in sizes:
        for seed in seeds:
            row = measure(arguments.agent_a, arguments.agent_b, size, seed, histories)
            rows.append(row)
            print(f"size {size} seed {seed}: {'error' if 'error' in row else 'ok'}")
    names = (arguments.agent_a.stem, arguments.agent_b.stem)
    environment = {
        "python": platform.python_version(),
        "os": platform.platform(),
        "processor": platform.processor(),
    }
    report = {"environment": environment, "agents": names, "matches": rows}
    (arguments.output_dir / "metrics.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8"
    )
    summary = summarise(rows, names)
    (arguments.output_dir / "metrics.md").write_text(summary + "\n", encoding="utf-8")
    print(json.dumps(environment))
    print(summary)
    return 1 if any("error" in row for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
