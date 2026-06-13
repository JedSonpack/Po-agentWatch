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


def _read_last_messages_from_transcript(transcript_path: str) -> tuple[str, str]:
    """从 Claude 的 transcript JSONL 读取最后一条 assistant 消息和最后一条 user 消息。

    Claude Code 的 hook 事件不直接带消息内容，需要从 transcript 文件解析。
    返回 (last_assistant_message, last_user_message)，读不到就返回空字符串。
    """
    try:
        path = Path(transcript_path).expanduser()
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, FileNotFoundError):
        return "", ""

    last_assistant = ""
    last_user = ""
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # Anthropic content blocks: [{"type":"text","text":"..."}]
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            text = "\n".join(parts)
        if not text:
            continue
        if role == "assistant":
            last_assistant = text
        elif role == "user":
            last_user = text
    return last_assistant, last_user


def normalize_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """把不同 Agent 的事件归一化成 Codex 形态，方便下游统一渲染。

    支持：
    - Codex: type=agent-turn-complete (原生格式，直接返回)
    - Claude Code: hook_event_name=Stop (从 transcript_path 提取消息后转换)

    返回 None 表示这个事件不是任务完成事件，应该忽略。
    """
    # Codex 原生格式
    if event.get("type") == "agent-turn-complete":
        return event

    # Claude Code Stop hook
    if event.get("hook_event_name") == "Stop":
        transcript = str(event.get("transcript_path", "")).strip()
        last_assistant, last_user = _read_last_messages_from_transcript(transcript)
        return {
            "type": "agent-turn-complete",
            "cwd": str(event.get("cwd", "")),
            "last-assistant-message": last_assistant or "任务已完成。",
            "input-messages": [last_user] if last_user else [],
        }

    return None


def handle_event(
    event: dict[str, Any],
    config: dict[str, Any],
    sender: Sender | None = None,
) -> str:
    normalized = normalize_event(event)
    if normalized is None:
        return "ignored"

    rendered = render_message(normalized, config.get("message", {}))
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
