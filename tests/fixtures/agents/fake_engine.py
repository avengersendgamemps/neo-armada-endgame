"""Stand-in for the engine process in client launcher tests.

Usage: fake_engine.py MODE OUTPUT [DELAY_SECONDS] [SOURCE_HISTORY]

Modes:
  ok          wait DELAY, copy SOURCE_HISTORY to OUTPUT, report success, exit 0
  not_found   report "agent not found" as the engine does, exit 3
  crash       write a traceback-like text to stderr only, exit 70
  no_history  report success without writing OUTPUT, exit 0
  silent_ok   exit 0 without printing anything
  hang        sleep for a long time
"""

import json
import shutil
import sys
import time


def main() -> int:
    mode, output = sys.argv[1], sys.argv[2]
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    time.sleep(delay)
    if mode == "ok":
        shutil.copyfile(sys.argv[4], output)
        print(json.dumps({"status": "ok", "cli_version": 1, "history": output}))
        return 0
    if mode == "not_found":
        print(
            json.dumps(
                {
                    "status": "error",
                    "cli_version": 1,
                    "code": 3,
                    "message": "agent not found: nowhere.py",
                }
            )
        )
        return 3
    if mode == "crash":
        sys.stderr.write("RuntimeError: simulated engine crash\n")
        return 70
    if mode == "no_history":
        print(json.dumps({"status": "ok", "cli_version": 1, "history": output}))
        return 0
    if mode == "silent_ok":
        return 0
    if mode == "hang":
        time.sleep(3600)
    return 2


if __name__ == "__main__":
    sys.exit(main())
