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


# 仓库根目录：agent_watch/server.py → 上两级。这样无论用户把仓库放在哪、
# 从哪个目录启动服务，notify_watch.py 路径都能正确解析。
REPO_ROOT = Path(__file__).resolve().parent.parent


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
    # 把保存路径返回给前端，便于给用户显示「保存到了哪里」
    return {"ok": True, "config": merged, "saved_path": str(path.resolve())}


def build_install_snippet(notify_script: Path) -> dict[str, str]:
    script = str(notify_script.resolve())
    # 用同一份 SAMPLE_EVENT 生成测试命令，确保「预览看到什么、命令跑出来就是什么」
    sample_json = json.dumps(SAMPLE_EVENT, ensure_ascii=False, separators=(",", ":"))
    # shell 单引号包裹 JSON，需要把 JSON 内的单引号转义为 '\''
    escaped_for_shell = sample_json.replace("'", "'\\''")
    return {
        "toml": f'notify = ["python3", "{script}"]',
        "intro": (
            "Codex 在每个任务结束时会调用 notify 配置里的命令，把事件信息作为 JSON 传过来。"
            "下面两步教你把 Agent Watch 接到 Codex；本工具不会自动修改你的 Codex 全局配置。"
        ),
        "step1_title": "步骤 1：把下面这一行加到 ~/.codex/config.toml",
        "step1_desc": "这行配置告诉 Codex：每次任务结束，就用 python3 调用 notify_watch.py，由它把事件转换成 Bark 推送。",
        "step2_title": "步骤 2（可选）：在终端先测一下脚本能不能跑通",
        "step2_desc": (
            "下面这条命令模拟了 Codex 真实调用时传给脚本的 JSON 事件，"
            "用的就是上方「预览」里看到的同一份示例数据。"
            "执行后你的手机应该会收到与预览一致的 Bark 通知；"
            "如果收不到，说明脚本或 Bark 配置有问题，不用动 Codex 就能排查。"
        ),
        "test_command": f"python3 {script} '{escaped_for_shell}'",
        # 兼容旧字段，保持 API 不破坏现有调用方
        "note": (
            "Codex 在每个任务结束时会调用 notify 配置里的命令。"
            "请手动把下方的 notify 配置加入 ~/.codex/config.toml；本工具不会自动修改你的 Codex 全局配置。"
        ),
    }


class RequestHandler(BaseHTTPRequestHandler):
    config_path = REPO_ROOT / ".agent-watch" / "config.json"
    static_dir = Path(__file__).parent / "static"
    notify_script = REPO_ROOT / "notify_watch.py"

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
