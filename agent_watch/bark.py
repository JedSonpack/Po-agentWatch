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


def _build_direct_opener() -> urllib.request.OpenerDirector:
    """构造一个绕开系统代理 / 环境变量代理的 opener。

    Bark 的服务（api.day.app 或自部署）通常是国内可直连的服务，
    走代理反而会引发 SSL 握手超时（特别是用户开了 Clash 等工具时）。
    显式塞一个空 ProxyHandler 让 urllib 不读 macOS 系统代理设置。
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def send_bark(
    bark_config: dict[str, Any],
    title: str,
    body: str,
    opener: Callable[..., Any] | None = None,
) -> None:
    request = build_bark_request(bark_config, title, body)
    urlopen = opener or _build_direct_opener().open
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            response.read()
    except BarkError:
        raise
    except Exception as exc:
        raise BarkError(f"Bark 推送失败：{exc}") from exc
