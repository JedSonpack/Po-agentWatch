#!/usr/bin/env python3
from __future__ import annotations

import sys

from agent_watch.notify import main as notify_main


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "notify":
        return notify_main(sys.argv[2:])
    if command == "serve":
        from agent_watch.server import main as server_main

        return server_main(sys.argv[2:])
    print("用法：python3 agent_watch.py serve | notify <event-json> [config-path]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
