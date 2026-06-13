from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_CONFIG: dict[str, Any] = {
    "bark": {
        "server": "https://api.day.app",
        "key": "",
        "level": "timeSensitive",
        "sound": "bell",
        "icon": "",
    },
    "message": {
        "title_template": "Agent 已完成：{project}",
        "body_template": "{summary}",
        "max_body_chars": 160,
    },
}


def default_config_path(base_dir: Path | None = None) -> Path:
    """配置默认存在 ~/.agent-watch/config.json（用户级，跨项目共用）。

    早期版本曾把配置存在仓库内 .agent-watch/，但 Codex 的 notify 命令和
    Claude Code 的 hook 触发时 cwd 都是当前会话目录、不是 agent-watch 仓库本身，
    导致从其它项目调起来时读不到 Bark Key、推送被静默 skip。

    现在默认走 $HOME，仓库挪位置 / 重新 clone 都不影响配置；项目本地
    .agent-watch/config.json 仍可显式作为覆盖（传 base_dir 进来时使用）。
    """
    if base_dir is not None:
        local = base_dir / ".agent-watch" / "config.json"
        if local.exists():
            return local
    return Path.home() / ".agent-watch" / "config.json"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or default_config_path()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return copy.deepcopy(DEFAULT_CONFIG)
    except json.JSONDecodeError:
        return copy.deepcopy(DEFAULT_CONFIG)

    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULT_CONFIG)
    return _deep_merge(DEFAULT_CONFIG, raw)


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_config(config: dict[str, Any]) -> list[str]:
    if not isinstance(config, dict):
        return ["配置必须是对象。"]

    errors: list[str] = []
    bark = config.get("bark", {})
    message = config.get("message", {})

    if not isinstance(bark, dict):
        errors.append("Bark 配置必须是对象。")
        bark = copy.deepcopy(DEFAULT_CONFIG["bark"])

    if not isinstance(message, dict):
        errors.append("消息配置必须是对象。")
        message = copy.deepcopy(DEFAULT_CONFIG["message"])

    server = str(bark.get("server", "")).strip()
    parsed_server = urlparse(server)
    if not server or parsed_server.scheme not in {"http", "https"} or not parsed_server.netloc:
        errors.append("Bark Server 必须是有效的 http 或 https 地址。")

    icon = str(bark.get("icon", "")).strip()
    if icon:
        parsed_icon = urlparse(icon)
        if parsed_icon.scheme not in {"http", "https"} or not parsed_icon.netloc:
            errors.append("Logo URL 必须是有效的 http 或 https 地址。")

    max_body_chars = message.get("max_body_chars")
    if not isinstance(max_body_chars, int) or max_body_chars < 20:
        errors.append("消息正文长度至少为 20 个字符。")
    elif max_body_chars > 500:
        errors.append("消息正文长度最多为 500 个字符。")

    for field_name, label in (
        ("title_template", "标题模板"),
        ("body_template", "正文模板"),
    ):
        if not str(message.get(field_name, "")).strip():
            errors.append(f"{label}不能为空。")

    return errors
