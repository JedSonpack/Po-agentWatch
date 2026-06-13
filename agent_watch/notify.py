from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from .bark import BarkError, send_bark
from .config import load_config
from .templates import render_message


Sender = Callable[[dict[str, Any], str, str], None]


def load_event_from_text(raw: str) -> dict[str, Any] | None:
    if not raw.strip():
        print("notify_watch: no JSON payload provided; skipping notification.")
        return None
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"notify_watch: invalid JSON payload ({exc.msg}); skipping notification.")
        return None
    if not isinstance(event, dict):
        print("notify_watch: JSON payload must be an object; skipping notification.")
        return None
    return event


def handle_event(
    event: dict[str, Any],
    config: dict[str, Any],
    sender: Sender | None = None,
) -> str:
    if event.get("type") != "agent-turn-complete":
        return "ignored"

    rendered = render_message(event, config.get("message", {}))
    bark_config = config.get("bark", {})
    send = sender or send_bark
    try:
        send(bark_config, rendered["title"], rendered["body"])
    except (BarkError, ValueError) as exc:
        print(f"notify_watch: {exc}; skipping notification.")
        return "failed"
    return "sent"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    raw = args[0] if args else sys.stdin.read()
    event = load_event_from_text(raw)
    if event is None:
        return 0

    config_path = Path(args[1]).expanduser() if len(args) > 1 else None
    config = load_config(config_path)
    handle_event(event, config)
    return 0
