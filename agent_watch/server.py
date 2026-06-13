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


def build_install_snippet(notify_script: Path) -> dict[str, Any]:
    script = str(notify_script.resolve())
    # 用同一份 SAMPLE_EVENT 生成测试命令，确保「预览看到什么、命令跑出来就是什么」
    sample_json = json.dumps(SAMPLE_EVENT, ensure_ascii=False, separators=(",", ":"))
    # shell 单引号包裹 JSON，需要把 JSON 内的单引号转义为 '\''
    escaped_for_shell = sample_json.replace("'", "'\\''")

    # Claude Code 的 hook 配置片段（settings.json）
    # 同时挂 Stop（任务完成）和 Notification（等你授权 / 等你输入）
    # 两个时机的标题不同：Stop=「Agent 已完成...」、Notification=「⏸ Claude 等你确认...」
    claude_settings = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {script}",
                        }
                    ]
                }
            ],
            "Notification": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python3 {script}",
                        }
                    ]
                }
            ],
        }
    }
    claude_settings_text = json.dumps(claude_settings, ensure_ascii=False, indent=2)

    intro = (
        "Agent Watch 通过订阅 Agent 的「任务完成」事件来推送通知。"
        "下面给出 Codex 和 Claude Code 两种主流 Agent 的接入方法；"
        "本工具不会自动修改你的全局配置，需要手动复制粘贴。"
    )

    agents = [
        {
            "id": "codex",
            "label": "Codex",
            "intro": (
                "Codex（OpenAI Agent CLI）在每个任务（turn）结束时调用 notify 配置里的命令。"
                "Codex 的事件模型只有 agent-turn-complete 一种——它没有 Claude Code 那样的"
                "「等待用户授权」独立事件，是在 TUI 里直接阻塞等输入、不调外部 notify。"
                "所以下面一行就够了，不需要挂多个 hook 点。"
            ),
            "step1_title": "步骤 1：把下面这一行加到 ~/.codex/config.toml",
            "step1_desc": (
                "这行配置告诉 Codex：每次任务结束，就用 python3 调用 notify_watch.py，"
                "由它把事件转换成 Bark 推送。"
            ),
            "step1_code": f'notify = ["python3", "{script}"]',
            "step1_lang": "toml",
            "step2_title": "步骤 2（可选）：在终端先测一下脚本能不能跑通",
            "step2_desc": (
                "这条命令模拟了 Codex 真实调用时传给脚本的 JSON 事件，"
                "用的就是上方「预览」里看到的同一份示例数据。"
                "执行后你的手机应该收到一条与预览一致的 Bark 通知。"
            ),
            "step2_code": f"python3 {script} '{escaped_for_shell}'",
            "step2_lang": "bash",
        },
        {
            "id": "claude",
            "label": "Claude Code",
            "intro": (
                "Claude Code 通过 hook 触发命令，事件 JSON 通过 stdin 传给脚本。"
                "下面同时配置了两个 hook 点："
                "Stop（主回复结束 = 任务跑完）和 Notification（Claude 主动弹窗，"
                "通常是请求权限或长时间空闲），各自的通知标题会自动区分。"
                "想只接其一可删掉对应数组。"
            ),
            "step1_title": "步骤 1：把下面的 hooks 配置合并进 ~/.claude/settings.json",
            "step1_desc": (
                "如果 settings.json 已存在 hooks 节点，把 Stop / Notification 数组追加进去；"
                "否则直接用下面这段做整个文件。"
                "Stop 让你知道「任务跑完了」，Notification 让你知道「Claude 卡在等你了」。"
            ),
            "step1_code": claude_settings_text,
            "step1_lang": "json",
            "step2_title": "步骤 2（可选）：在终端模拟两种 Claude 事件各跑一次",
            "step2_desc": (
                "Claude 是通过 stdin 传 JSON 的，所以这里用 echo 管道输入。"
                "下面给了两条命令：第一条模拟 Stop（任务跑完），第二条模拟 Notification"
                "（Claude 等你确认）。两条都跑一遍，应该收到两条标题不同的推送，证明两个"
                "hook 点都打通了。transcript_path 给个不存在的路径也没关系，脚本会优雅"
                "降级成「任务已完成。」。"
            ),
            "step2_code": (
                "# 测 Stop（任务跑完）\n"
                "echo '{\"hook_event_name\":\"Stop\","
                "\"transcript_path\":\"/tmp/nope.jsonl\","
                "\"cwd\":\"/Users/demo/project/agent-watch\","
                "\"session_id\":\"demo\"}' | "
                f"python3 {script}\n\n"
                "# 测 Notification（Claude 等你确认）\n"
                "echo '{\"hook_event_name\":\"Notification\","
                "\"message\":\"Claude needs permission to use Bash\","
                "\"cwd\":\"/Users/demo/project/agent-watch\","
                "\"session_id\":\"demo\"}' | "
                f"python3 {script}"
            ),
            "step2_lang": "bash",
        },
    ]

    return {
        "intro": intro,
        "agents": agents,
        # ----- 兼容字段，保留旧前端不报错 -----
        "toml": agents[0]["step1_code"],
        "step1_title": agents[0]["step1_title"],
        "step1_desc": agents[0]["step1_desc"],
        "step2_title": agents[0]["step2_title"],
        "step2_desc": agents[0]["step2_desc"],
        "test_command": agents[0]["step2_code"],
        "note": (
            "Codex / Claude Code 任务结束时会调用 notify 配置里的命令。"
            "请手动把下方的配置加入对应的全局配置文件；本工具不会自动修改你的 Agent 全局配置。"
        ),
    }


class RequestHandler(BaseHTTPRequestHandler):
    # 配置默认存到 ~/.agent-watch/config.json（用户级），所有项目共用同一份。
    # Codex notify 和 Claude Code hook 在任意 cwd 下都能读到，不再需要每个项目复制一份。
    config_path = Path.home() / ".agent-watch" / "config.json"
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
