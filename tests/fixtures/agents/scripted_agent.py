"""Deliberately faulty agent for runtime tests.

Usage: scripted_agent.py MODE [DELAY_SECONDS]   (DELAY defaults to 1.5)

Modes:
  ok            answers every tick with an empty command list
  never_ready   reads init, never answers
  bad_ready     answers init with garbage
  wrong_version answers ready with protocol_version 99
  exit_on_init  exits before answering init
  silent        ready, then never answers ticks (keeps reading)
  hang          ready, then stops reading and sleeps forever
  slow          ready, then answers every tick after DELAY
  slow_twice    slow for ticks 1-2, fast afterwards
  late_once     tick 1 answered after DELAY, later ticks immediately
  crash         ready, then exits with code 3 on the first tick
  crash_at_3    answers ticks 1-2, exits on tick 3
  malformed     answers every tick with a non-JSON line
  future_tick   answers with tick + 5
  oversize      answers tick 1 with a 200 kB line, then behaves
  stderr_flood  writes 3 MB to stderr every tick, answers normally
  stdout_flood  ready, then prints garbage lines forever without reading
  memory_hog    ready, then allocates ~4 GiB on the first tick
  move_east     moves its first ship east every tick
"""

import json
import sys
import time


def send(obj) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    player = 0
    for raw in sys.stdin:
        message = json.loads(raw)
        kind = message["type"]
        if kind == "init":
            player = message["player_id"]
            if mode == "never_ready":
                time.sleep(3600)
            elif mode == "bad_ready":
                sys.stdout.write("READY!\n")
                sys.stdout.flush()
            elif mode == "wrong_version":
                send({"type": "ready", "protocol_version": 99})
            elif mode == "exit_on_init":
                return 4
            else:
                send({"type": "ready", "protocol_version": 1})
            if mode == "stdout_flood":
                while True:
                    sys.stdout.write("garbage " * 100 + "\n")
            continue
        if kind == "end":
            return 0
        tick = message["tick"]
        reply = {"type": "commands", "tick": tick, "moves": [], "build": False}
        if mode == "silent":
            continue
        if mode == "hang":
            time.sleep(3600)
        if mode == "slow" or (mode == "slow_twice" and tick <= 2):
            time.sleep(delay)
        if mode == "late_once" and tick == 1:
            time.sleep(delay)
        if mode == "crash" or (mode == "crash_at_3" and tick == 3):
            sys.stderr.write("scripted crash\n")
            return 3
        if mode == "malformed":
            sys.stdout.write("}{ not json\n")
            sys.stdout.flush()
            continue
        if mode == "future_tick":
            reply["tick"] = tick + 5
        if mode == "oversize" and tick == 1:
            reply["padding"] = "x" * 200_000
        if mode == "stderr_flood":
            sys.stderr.write("e" * 3_000_000)
            sys.stderr.flush()
        if mode == "memory_hog":
            hog = [bytearray(64 * 1024 * 1024) for _ in range(64)]
            reply["hog"] = len(hog)
        if mode == "move_east":
            mine = [s for s in message["ships"] if s["owner"] == player]
            if mine:
                reply["moves"] = [{"ship": mine[0]["id"], "action": "E"}]
        send(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
