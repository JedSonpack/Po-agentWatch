from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from .bark import BarkError, send_bark
from .config import load_config
from .templates import project_name, render_message, shorten


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

    时序坑：Claude Code 的 Stop hook 可能在「本轮 assistant 文本落盘」之前触发，
    此时 transcript 末尾只有本轮 user 消息，最后一条 assistant 仍是**上一轮**的。
    若直接返回这段陈旧 assistant，会推送出「本轮 user + 上一轮 assistant」的错配。
    解决：记录二者出现的行号，若 last_user 位置在 last_assistant 之后，认为本轮
    assistant 尚未写入，主动丢弃陈旧 assistant，让上层走 "任务已完成。" 兜底。

    返回 (last_assistant_message, last_user_message)，读不到就返回空字符串。
    """
    try:
        path = Path(transcript_path).expanduser()
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, FileNotFoundError):
        return "", ""

    last_assistant = ""
    last_assistant_idx = -1
    last_user = ""
    last_user_idx = -1
    for idx, line in enumerate(lines):
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
            last_assistant_idx = idx
        elif role == "user":
            last_user = text
            last_user_idx = idx

    # 若本轮 user 在 last_assistant 之后才出现，说明本轮 assistant 尚未落盘，
    # 拿到的 last_assistant 是上一轮的 —— 丢弃避免错配。
    if last_user_idx > last_assistant_idx:
        last_assistant = ""

    return last_assistant, last_user


def normalize_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """把不同 Agent 的事件归一化成 Codex 形态，方便下游统一渲染。

    支持：
    - Codex: type=agent-turn-complete (原生格式，直接返回)
    - Claude Code Stop hook: hook_event_name=Stop (从 transcript_path 提取消息后转换)
    - Claude Code Notification hook: hook_event_name=Notification
      （等待授权 / 等待输入时触发，event 自带 message 字段，无 transcript）

    返回 None 表示这个事件不是要推送的事件，应该忽略。
    """
    # Codex 原生格式
    if event.get("type") == "agent-turn-complete":
        return event

    # Claude Code Stop hook：主回复结束
    if event.get("hook_event_name") == "Stop":
        transcript = str(event.get("transcript_path", "")).strip()
        last_assistant, last_user = _read_last_messages_from_transcript(transcript)
        return {
            "type": "agent-turn-complete",
            "cwd": str(event.get("cwd", "")),
            "last-assistant-message": last_assistant or "任务已完成。",
            "input-messages": [last_user] if last_user else [],
        }

    # Claude Code Notification hook：Claude 主动发系统通知（请求权限 / 等待输入 / 长时间空闲）
    # 必须用独立标题，不能跟 Stop 共用「Agent 已完成」—— 否则你会以为任务跑完了，
    # 结果 Claude 还在等你确认。
    if event.get("hook_event_name") == "Notification":
        message = str(event.get("message", "")).strip() or "Claude 等待你的输入"
        cwd = str(event.get("cwd", ""))
        # 渲染好成品塞回 last-assistant-message 字段，
        # 让下游 templates 走「summary 已就绪」的路径，但通过 _title 字段强制覆盖标题。
        return {
            "type": "claude-notification",
            "cwd": cwd,
            "last-assistant-message": message,
            "input-messages": [],
            # 自定义渲染参数：handle_event 会优先使用这两个字段而不是模板
            "_title": f"⏸ Claude 等你确认：{project_name(cwd)}",
            "_body": shorten(message, 160),
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

    # 部分事件（如 Claude Notification）希望绕过用户模板，
    # 用脚本预渲染好的标题和正文 —— 否则用户的 "Agent 已完成" 模板会误导。
    forced_title = normalized.get("_title")
    forced_body = normalized.get("_body")
    if forced_title and forced_body:
        title, body = str(forced_title), str(forced_body)
    else:
        rendered = render_message(normalized, config.get("message", {}))
        title, body = rendered["title"], rendered["body"]

    bark_config = config.get("bark", {})
    send = sender or send_bark
    try:
        send(bark_config, title, body)
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
