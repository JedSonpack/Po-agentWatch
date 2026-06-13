from __future__ import annotations

import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .bark import BarkError, send_bark
from .config import load_config, save_config, validate_config
from .templates import render_message


SAMPLE_EVENT = {
    "type": "agent-turn-complete",
    "cwd": "/Users/demo/project/agent-watch",
    "last-assistant-message": "任务已完成，关键检查已通过。",
    "input-messages": ["请实现手表通知 UI"],
}


def preview_payload(config: dict[str, Any]) -> dict[str, Any]:
    rendered = render_message(SAMPLE_EVENT, config.get("message", {}))
    icon = str(config.get("bark", {}).get("icon", "")).strip()
    return {
        "watch": rendered,
        "phone": {**rendered, "icon": icon},
    }


def save_config_payload(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    current = load_config(path)
    merged = {**current, **payload}
    if isinstance(current.get("bark"), dict) and isinstance(payload.get("bark"), dict):
        merged["bark"] = {**current["bark"], **payload["bark"]}
    if isinstance(current.get("message"), dict) and isinstance(payload.get("message"), dict):
        merged["message"] = {**current["message"], **payload["message"]}

    errors = validate_config(merged)
    if errors:
        return {"ok": False, "errors": errors}
    save_config(merged, path)
    return {"ok": True, "config": merged}


def build_install_snippet(notify_script: Path) -> dict[str, str]:
    script = str(notify_script.resolve())
    return {
        "toml": f'notify = ["python3", "{script}"]',
        "note": "请手动把上面的 notify 配置加入 ~/.codex/config.toml；本工具不会自动修改你的 Codex 全局配置。",
        "test_command": (
            "python3 "
            + script
            + " '{\"type\":\"agent-turn-complete\",\"cwd\":\"/tmp/agent-watch\",\"last-assistant-message\":\"测试通知已发送。\",\"input-messages\":[\"测试\"]}'"
        ),
    }


class RequestHandler(BaseHTTPRequestHandler):
    config_path = Path.cwd() / ".agent-watch" / "config.json"
    static_dir = Path(__file__).parent / "static"
    notify_script = Path.cwd() / "notify_watch.py"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象。")
        return data

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._json(200, {"config": load_config(self.config_path)})
            return
        if parsed.path == "/api/preview":
            self._json(200, preview_payload(load_config(self.config_path)))
            return
        if parsed.path == "/api/install-snippet":
            self._json(200, build_install_snippet(self.notify_script))
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/api/config":
                result = save_config_payload(payload, self.config_path)
                self._json(200 if result["ok"] else 400, result)
                return
            if self.path == "/api/preview":
                errors = validate_config(payload)
                if errors:
                    self._json(400, {"ok": False, "errors": errors})
                    return
                self._json(200, preview_payload(payload))
                return
            if self.path == "/api/test-send":
                config = payload or load_config(self.config_path)
                errors = validate_config(config)
                if errors:
                    self._json(400, {"ok": False, "errors": errors})
                    return
                rendered = render_message(SAMPLE_EVENT, config.get("message", {}))
                send_bark(config.get("bark", {}), rendered["title"], rendered["body"])
                self._json(200, {"ok": True, "message": "测试通知已发送。"})
                return
            self._json(404, {"ok": False, "errors": ["接口不存在。"]})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "errors": [str(exc)]})
        except BarkError as exc:
            self._json(400, {"ok": False, "errors": [str(exc)]})

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        path = (self.static_dir / relative).resolve()
        if not str(path).startswith(str(self.static_dir.resolve())) or not path.exists():
            self.send_error(404)
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main(argv: list[str] | None = None) -> int:
    args = argv or []
    port = int(args[0]) if args else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), RequestHandler)
    print(f"Agent Watch UI: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止 Agent Watch UI。")
    return 0
