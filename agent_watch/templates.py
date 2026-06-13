from __future__ import annotations

import json
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_VARIABLES = {"project", "summary", "last_input", "cwd", "time"}


def collapse_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    value = re.sub(r"```.*?```", " [代码省略] ", value, flags=re.DOTALL)
    value = re.sub(r"```[\s\S]*$", " [代码省略] ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def shorten(text: Any, max_chars: int) -> str:
    collapsed = collapse_text(text)
    if len(collapsed) <= max_chars:
        return collapsed

    if max_chars <= 0:
        return ""

    ellipsis = "..."[:max_chars]
    budget = max_chars - len(ellipsis)
    if budget <= 0:
        return ellipsis

    candidate = collapsed[:budget].rstrip()
    split_at = max(candidate.rfind(mark) for mark in ("。", "！", "？", ".", "!", "?", "；", ";"))
    if split_at >= max(2, budget // 3):
        candidate = candidate[: split_at + 1].rstrip()
    else:
        candidate = candidate.rstrip("，,、:：;；")
    return candidate + ellipsis


def project_name(cwd: Any) -> str:
    cwd_text = str(cwd or "").strip()
    if not cwd_text:
        return "未知项目"
    return Path(cwd_text).expanduser().name or cwd_text


def last_input_summary(input_messages: Any) -> str:
    if not isinstance(input_messages, list) or not input_messages:
        return ""
    return shorten(input_messages[-1], 80)


def variables_for_event(event: dict[str, Any]) -> dict[str, str]:
    summary = shorten(event.get("last-assistant-message", ""), 130)
    fallback = last_input_summary(event.get("input-messages", []))
    if not summary:
        summary = f"已处理：{fallback}" if fallback else "任务已完成。"

    return {
        "project": project_name(event.get("cwd")),
        "summary": summary,
        "last_input": fallback,
        "cwd": collapse_text(event.get("cwd", "")),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _validate_template(template: str) -> None:
    formatter = string.Formatter()
    try:
        parts = list(formatter.parse(template))
    except ValueError as exc:
        raise ValueError(f"模板格式无效：{exc}") from None

    for _, field_name, format_spec, conversion in parts:
        if field_name is None:
            continue
        if field_name == "":
            raise ValueError("模板格式无效：只支持裸变量。")
        if conversion or format_spec:
            raise ValueError("模板格式无效：只支持裸变量。")
        if field_name and field_name not in SUPPORTED_VARIABLES:
            raise ValueError(f"未知模板变量：{field_name}")


def render_message(event: dict[str, Any], message_config: dict[str, Any]) -> dict[str, str]:
    title_template = str(message_config.get("title_template", "Codex 已完成：{project}"))
    body_template = str(message_config.get("body_template", "{summary}"))
    max_body_chars = int(message_config.get("max_body_chars", 160))

    _validate_template(title_template)
    _validate_template(body_template)

    variables = variables_for_event(event)
    try:
        title = collapse_text(title_template.format(**variables))
        body = shorten(body_template.format(**variables), max_body_chars)
    except ValueError as exc:
        raise ValueError(f"模板格式无效：{exc}") from None
    return {"title": title, "body": body}
