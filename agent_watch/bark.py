from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Any, Callable


HTTP_TIMEOUT_SECONDS = 8


class BarkError(RuntimeError):
    pass


def build_bark_request(bark_config: dict[str, Any], title: str, body: str) -> urllib.request.Request:
    key = str(bark_config.get("key", "")).strip()
    if not key:
        raise BarkError("Bark Key 不能为空。")

    server = str(bark_config.get("server", "https://api.day.app")).strip().rstrip("/")
    url = f"{server}/{urllib.parse.quote(key, safe='')}"
    payload = {
        "title": title,
        "body": body,
        "level": str(bark_config.get("level", "timeSensitive") or "timeSensitive"),
        "sound": str(bark_config.get("sound", "bell") or "bell"),
    }
    icon = str(bark_config.get("icon", "")).strip()
    if icon:
        payload["icon"] = icon

    data = urllib.parse.urlencode(payload).encode("utf-8")
    return urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )


def send_bark(
    bark_config: dict[str, Any],
    title: str,
    body: str,
    opener: Callable[..., Any] | None = None,
) -> None:
    request = build_bark_request(bark_config, title, body)
    urlopen = opener or urllib.request.urlopen
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            response.read()
    except BarkError:
        raise
    except Exception as exc:
        raise BarkError(f"Bark 推送失败：{exc}") from exc
