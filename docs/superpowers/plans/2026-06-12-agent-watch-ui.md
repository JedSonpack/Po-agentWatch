# Agent Watch UI 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个面向中文用户的 Python 本地 Web UI，让用户定制 Codex 完成通知的 Bark 消息格式、预览手表/手机效果、测试发送，并复制手动安装到 Codex 的配置片段。

**架构：** 使用 Python 标准库实现一个小型本地 Web 服务和通知脚本。核心逻辑拆成配置加载、模板渲染、Bark 客户端、Codex 事件处理、Web API、静态 UI 六个边界；UI 只写本项目本地配置，不自动修改 `~/.codex/config.toml`。

**技术栈：** Python 3 标准库、`unittest`、原生 HTML/CSS/JavaScript、Bark HTTP API。

---

## 文件结构

- 创建：`agent_watch/__init__.py`  
  包标记，导出版本号。
- 创建：`agent_watch/config.py`  
  默认配置、配置路径、读取、保存、深度合并、基础校验。
- 创建：`agent_watch/templates.py`  
  Codex 事件变量提取、文本折叠、截断、模板渲染。
- 创建：`agent_watch/bark.py`  
  Bark payload 构造和 HTTP 发送；支持测试注入 opener，避免测试真实联网。
- 创建：`agent_watch/notify.py`  
  Codex notify 入口逻辑：读取事件、忽略非完成事件、加载配置、渲染并发送，失败软退出。
- 创建：`agent_watch/server.py`  
  本地 Web 服务和 JSON API。
- 创建：`agent_watch/static/index.html`  
  单页左右布局 UI，中文文案。
- 创建：`agent_watch/static/styles.css`  
  UI 样式，桌面/移动响应式。
- 创建：`agent_watch/static/app.js`  
  配置表单、变量插入、预览、保存、测试发送、安装片段展示。
- 创建：`agent_watch.py`  
  CLI 入口：`serve` 和 `notify`。
- 创建或替换：`notify_watch.py`  
  仓库内可提交的 Codex notify wrapper，调用 `agent_watch.notify`。当前工作区里这个文件是指向 `~/.codex/notify_watch.py` 的符号链接；实现时需要把它替换成真实文件，不能修改链接目标文件。
- 创建：`examples/config.example.json`  
  无密钥示例配置。
- 创建：`tests/test_config.py`  
  配置默认值、保存、合并、校验测试。
- 创建：`tests/test_templates.py`  
  变量提取、模板渲染、未知变量、截断测试。
- 创建：`tests/test_bark.py`  
  Bark payload 和 HTTP 发送测试，使用 fake opener。
- 创建：`tests/test_notify.py`  
  Codex notify 事件处理测试，使用 fake send。
- 创建：`tests/test_server.py`  
  Web API 轻量测试，验证配置、预览、安装片段响应。
- 修改：`.gitignore`  
  保持 `.agent-watch/` 忽略，必要时增加测试缓存。
- 修改：`codex-notify-watch.md`  
  更新为新项目结构说明。
- 创建：`README.md`  
  面向中文用户的快速开始、配置、测试发送、手动安装说明。

## 任务 1：配置模型和本地配置文件

**文件：**
- 创建：`agent_watch/__init__.py`
- 创建：`agent_watch/config.py`
- 创建：`examples/config.example.json`
- 创建：`tests/test_config.py`

- [ ] **步骤 1：编写失败的配置测试**

创建 `tests/test_config.py`：

```python
import json
import tempfile
import unittest
from pathlib import Path

from agent_watch.config import DEFAULT_CONFIG, load_config, save_config, validate_config


class ConfigTest(unittest.TestCase):
    def test_load_config_returns_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(Path(tmp) / ".agent-watch" / "config.json")

        self.assertEqual(config["bark"]["server"], "https://api.day.app")
        self.assertEqual(config["bark"]["level"], "timeSensitive")
        self.assertEqual(config["message"]["title_template"], "Codex 已完成：{project}")

    def test_load_config_merges_partial_user_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"message": {"max_body_chars": 80}}, ensure_ascii=False), encoding="utf-8")

            config = load_config(path)

        self.assertEqual(config["message"]["max_body_chars"], 80)
        self.assertEqual(config["bark"]["sound"], DEFAULT_CONFIG["bark"]["sound"])

    def test_save_config_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            config = load_config(path)
            config["bark"]["key"] = "abc123"

            save_config(config, path)

            stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["bark"]["key"], "abc123")

    def test_validate_config_rejects_invalid_max_body_chars(self):
        config = load_config(Path("/tmp/not-created.json"))
        config["message"]["max_body_chars"] = 5

        errors = validate_config(config)

        self.assertIn("消息正文长度至少为 20 个字符。", errors)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest tests.test_config -v`

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'agent_watch'`。

- [ ] **步骤 3：实现配置模块**

创建 `agent_watch/__init__.py`：

```python
__version__ = "0.1.0"
```

创建 `agent_watch/config.py`：

```python
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
        "title_template": "Codex 已完成：{project}",
        "body_template": "{summary}",
        "max_body_chars": 160,
    },
}


def default_config_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path.cwd()
    return root / ".agent-watch" / "config.json"


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
    errors: list[str] = []
    bark = config.get("bark", {})
    message = config.get("message", {})

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
```

创建 `examples/config.example.json`：

```json
{
  "bark": {
    "server": "https://api.day.app",
    "key": "",
    "level": "timeSensitive",
    "sound": "bell",
    "icon": ""
  },
  "message": {
    "title_template": "Codex 已完成：{project}",
    "body_template": "{summary}",
    "max_body_chars": 160
  }
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest tests.test_config -v`

预期：PASS，4 个测试通过。

- [ ] **步骤 5：Commit**

```bash
git add agent_watch/__init__.py agent_watch/config.py examples/config.example.json tests/test_config.py
git commit -m "Add local Agent Watch configuration"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 任务 2：模板渲染和手表优先截断

**文件：**
- 创建：`agent_watch/templates.py`
- 创建：`tests/test_templates.py`

- [ ] **步骤 1：编写失败的模板测试**

创建 `tests/test_templates.py`：

```python
import unittest

from agent_watch.templates import collapse_text, render_message, shorten


SAMPLE_EVENT = {
    "type": "agent-turn-complete",
    "cwd": "/Users/demo/work/agent-watch",
    "last-assistant-message": "任务已完成。\n\n```python\nprint('secret')\n```\n测试通过。",
    "input-messages": ["请实现通知 UI"],
}


class TemplateTest(unittest.TestCase):
    def test_collapse_text_removes_code_blocks_and_html(self):
        text = collapse_text("完成 <b>成功</b>\n```bash\necho token\n```")
        self.assertNotIn("echo token", text)
        self.assertIn("代码省略", text)
        self.assertEqual(text, "完成 成功 [代码省略]")

    def test_shorten_prefers_sentence_boundary(self):
        result = shorten("第一句很重要。第二句会被截断，因为内容太长。", 10)
        self.assertEqual(result, "第一句很重要。...")

    def test_render_message_uses_supported_variables(self):
        rendered = render_message(
            SAMPLE_EVENT,
            {
                "title_template": "Codex 已完成：{project}",
                "body_template": "{summary} / {last_input}",
                "max_body_chars": 80,
            },
        )
        self.assertEqual(rendered["title"], "Codex 已完成：agent-watch")
        self.assertIn("任务已完成", rendered["body"])
        self.assertIn("请实现通知 UI", rendered["body"])
        self.assertLessEqual(len(rendered["body"]), 80)

    def test_render_message_reports_unknown_variable(self):
        with self.assertRaises(ValueError) as ctx:
            render_message(
                SAMPLE_EVENT,
                {
                    "title_template": "{unknown}",
                    "body_template": "{summary}",
                    "max_body_chars": 80,
                },
            )
        self.assertIn("未知模板变量", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest tests.test_templates -v`

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'agent_watch.templates'`。

- [ ] **步骤 3：实现模板模块**

创建 `agent_watch/templates.py`：

```python
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
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def shorten(text: Any, max_chars: int) -> str:
    collapsed = collapse_text(text)
    if len(collapsed) <= max_chars:
        return collapsed

    candidate = collapsed[:max_chars].rstrip()
    split_at = max(candidate.rfind(mark) for mark in ("。", "！", "？", ".", "!", "?", "；", ";"))
    if split_at >= max(6, max_chars // 3):
        candidate = candidate[: split_at + 1].rstrip()
    else:
        candidate = candidate.rstrip("，,、:：;；")
    return candidate + "..."


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
    for _, field_name, _, _ in formatter.parse(template):
        if field_name and field_name not in SUPPORTED_VARIABLES:
            raise ValueError(f"未知模板变量：{field_name}")


def render_message(event: dict[str, Any], message_config: dict[str, Any]) -> dict[str, str]:
    title_template = str(message_config.get("title_template", "Codex 已完成：{project}"))
    body_template = str(message_config.get("body_template", "{summary}"))
    max_body_chars = int(message_config.get("max_body_chars", 160))

    _validate_template(title_template)
    _validate_template(body_template)

    variables = variables_for_event(event)
    title = collapse_text(title_template.format(**variables))
    body = shorten(body_template.format(**variables), max_body_chars)
    return {"title": title, "body": body}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest tests.test_templates -v`

预期：PASS，4 个测试通过。

- [ ] **步骤 5：Commit**

```bash
git add agent_watch/templates.py tests/test_templates.py
git commit -m "Render watch-first notification templates"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 任务 3：Bark 客户端

**文件：**
- 创建：`agent_watch/bark.py`
- 创建：`tests/test_bark.py`

- [ ] **步骤 1：编写失败的 Bark 测试**

创建 `tests/test_bark.py`：

```python
import unittest
from urllib.parse import parse_qs

from agent_watch.bark import BarkError, build_bark_request, send_bark


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"ok"


class FakeOpener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return FakeResponse()


class BarkTest(unittest.TestCase):
    def test_build_bark_request_includes_icon_and_message(self):
        request = build_bark_request(
            {
                "server": "https://api.day.app",
                "key": "device-key",
                "level": "timeSensitive",
                "sound": "bell",
                "icon": "https://example.com/logo.png",
            },
            "标题",
            "正文",
        )

        self.assertEqual(request.full_url, "https://api.day.app/device-key")
        payload = parse_qs(request.data.decode("utf-8"))
        self.assertEqual(payload["title"], ["标题"])
        self.assertEqual(payload["body"], ["正文"])
        self.assertEqual(payload["icon"], ["https://example.com/logo.png"])

    def test_send_bark_rejects_missing_key(self):
        with self.assertRaises(BarkError) as ctx:
            send_bark({"server": "https://api.day.app", "key": ""}, "标题", "正文")
        self.assertIn("Bark Key 不能为空", str(ctx.exception))

    def test_send_bark_uses_injected_opener(self):
        opener = FakeOpener()
        send_bark({"server": "https://api.day.app", "key": "abc"}, "标题", "正文", opener=opener)

        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(opener.requests[0][1], 8)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest tests.test_bark -v`

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'agent_watch.bark'`。

- [ ] **步骤 3：实现 Bark 客户端**

创建 `agent_watch/bark.py`：

```python
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
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest tests.test_bark -v`

预期：PASS，3 个测试通过。

- [ ] **步骤 5：Commit**

```bash
git add agent_watch/bark.py tests/test_bark.py
git commit -m "Add Bark delivery client"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 任务 4：Codex notify 脚本

**文件：**
- 创建：`agent_watch/notify.py`
- 创建或替换：`agent_watch.py`
- 创建或替换：`notify_watch.py`
- 创建：`tests/test_notify.py`

- [ ] **步骤 1：编写失败的 notify 测试**

创建 `tests/test_notify.py`：

```python
import json
import tempfile
import unittest
from pathlib import Path

from agent_watch.config import load_config, save_config
from agent_watch.notify import handle_event, load_event_from_text


class NotifyTest(unittest.TestCase):
    def test_load_event_from_text_rejects_non_object(self):
        self.assertIsNone(load_event_from_text("[]"))

    def test_handle_event_ignores_non_completion_event(self):
        calls = []
        result = handle_event({"type": "other"}, load_config(), sender=lambda *args: calls.append(args))

        self.assertEqual(result, "ignored")
        self.assertEqual(calls, [])

    def test_handle_event_renders_and_sends_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            config = load_config(path)
            config["bark"]["key"] = "abc"
            config["message"]["body_template"] = "{project}: {summary}"
            save_config(config, path)

            calls = []
            event = {
                "type": "agent-turn-complete",
                "cwd": "/tmp/agent-watch",
                "last-assistant-message": "完成。",
                "input-messages": ["做通知"],
            }
            result = handle_event(event, load_config(path), sender=lambda bark, title, body: calls.append((bark, title, body)))

        self.assertEqual(result, "sent")
        self.assertEqual(calls[0][1], "Codex 已完成：agent-watch")
        self.assertEqual(calls[0][2], "agent-watch: 完成。")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest tests.test_notify -v`

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'agent_watch.notify'`。

- [ ] **步骤 3：实现 notify 入口**

创建 `agent_watch/notify.py`：

```python
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
```

创建 `agent_watch.py`：

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys

from agent_watch.notify import main as notify_main


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "notify":
        return notify_main(sys.argv[2:])
    if command == "serve":
        from agent_watch.server import main as server_main

        return server_main(sys.argv[2:])
    print("用法：python3 agent_watch.py serve | notify <event-json> [config-path]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

将当前 `notify_watch.py` 符号链接替换成真实文件：

```python
#!/usr/bin/env python3
from __future__ import annotations

from agent_watch.notify import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest tests.test_notify -v`

预期：PASS，3 个测试通过。

- [ ] **步骤 5：手动验证 notify CLI**

运行：

```bash
python3 agent_watch.py notify '{"type":"agent-turn-complete","cwd":"/tmp/agent-watch","last-assistant-message":"任务已完成。","input-messages":["测试通知"]}' /tmp/missing-agent-watch-config.json
```

预期：退出码 0；如果没有 Bark Key，输出包含 `Bark Key 不能为空`。

- [ ] **步骤 6：Commit**

```bash
git add agent_watch/notify.py agent_watch.py notify_watch.py tests/test_notify.py
git commit -m "Handle Codex completion notifications"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 任务 5：本地 Web API

**文件：**
- 创建：`agent_watch/server.py`
- 创建：`tests/test_server.py`

- [ ] **步骤 1：编写失败的 server API 测试**

创建 `tests/test_server.py`：

```python
import json
import tempfile
import unittest
from pathlib import Path

from agent_watch.server import build_install_snippet, preview_payload, save_config_payload


class ServerTest(unittest.TestCase):
    def test_preview_payload_returns_watch_and_phone(self):
        payload = preview_payload(
            {
                "bark": {"icon": "https://example.com/logo.png"},
                "message": {
                    "title_template": "Codex 已完成：{project}",
                    "body_template": "{summary}",
                    "max_body_chars": 80,
                },
            }
        )

        self.assertEqual(payload["watch"]["title"], "Codex 已完成：agent-watch")
        self.assertIn("body", payload["phone"])
        self.assertEqual(payload["phone"]["icon"], "https://example.com/logo.png")

    def test_save_config_payload_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            result = save_config_payload({"bark": {"key": "abc"}}, path)

            stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(stored["bark"]["key"], "abc")

    def test_build_install_snippet_mentions_manual_config(self):
        snippet = build_install_snippet(Path("/repo/notify_watch.py"))

        self.assertIn('notify = ["python3", "/repo/notify_watch.py"]', snippet["toml"])
        self.assertIn("手动", snippet["note"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python3 -m unittest tests.test_server -v`

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'agent_watch.server'`。

- [ ] **步骤 3：实现 API 辅助函数和 HTTP 服务**

创建 `agent_watch/server.py`，包含以下公共函数和 `main`：

```python
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
```

在同一文件内继续实现 `RequestHandler`：

```python
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
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python3 -m unittest tests.test_server -v`

预期：PASS，3 个测试通过。

- [ ] **步骤 5：Commit**

```bash
git add agent_watch/server.py tests/test_server.py
git commit -m "Serve local Agent Watch configuration API"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 任务 6：中文单页 UI

**文件：**
- 创建：`agent_watch/static/index.html`
- 创建：`agent_watch/static/styles.css`
- 创建：`agent_watch/static/app.js`

- [ ] **步骤 1：创建 HTML 骨架**

创建 `agent_watch/static/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Watch</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <main class="shell">
    <section class="editor">
      <header>
        <p class="eyebrow">Agent Watch</p>
        <h1>定制 Codex 完成通知</h1>
        <p class="intro">为手表优先优化短提醒，同时保留手机 Bark 通知的 Logo、声音和通知级别。</p>
      </header>

      <form id="config-form">
        <fieldset>
          <legend>Bark 设置</legend>
          <label>Bark Server <input name="server" autocomplete="off"></label>
          <label>Bark Key <input name="key" type="password" autocomplete="off"></label>
          <label>Logo URL <input name="icon" autocomplete="off" placeholder="https://example.com/logo.png"></label>
          <div class="grid-2">
            <label>通知级别 <input name="level" autocomplete="off"></label>
            <label>声音 <input name="sound" autocomplete="off"></label>
          </div>
        </fieldset>

        <fieldset>
          <legend>消息模板</legend>
          <label>标题模板 <input name="title_template"></label>
          <label>正文模板 <textarea name="body_template" rows="4"></textarea></label>
          <label>手表正文长度 <input name="max_body_chars" type="number" min="20" max="500"></label>
          <div class="variables" aria-label="插入变量">
            <button type="button" data-var="{project}">项目名</button>
            <button type="button" data-var="{summary}">任务摘要</button>
            <button type="button" data-var="{last_input}">用户输入</button>
            <button type="button" data-var="{cwd}">工作目录</button>
            <button type="button" data-var="{time}">时间</button>
          </div>
        </fieldset>

        <div class="actions">
          <button type="submit">保存配置</button>
          <button type="button" id="test-send">发送测试通知</button>
        </div>
      </form>
    </section>

    <aside class="preview">
      <section>
        <h2>手表预览</h2>
        <div class="watch-face">
          <p id="watch-title"></p>
          <p id="watch-body"></p>
        </div>
      </section>

      <section>
        <h2>手机预览</h2>
        <div class="phone-card">
          <img id="phone-icon" alt="" hidden>
          <div>
            <p id="phone-title"></p>
            <p id="phone-body"></p>
          </div>
        </div>
      </section>

      <section>
        <h2>手动安装到 Codex</h2>
        <p id="install-note"></p>
        <pre><code id="install-toml"></code></pre>
        <pre><code id="test-command"></code></pre>
      </section>

      <p id="status" role="status"></p>
    </aside>
  </main>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **步骤 2：创建响应式样式**

创建 `agent_watch/static/styles.css`，重点要求：

```css
:root {
  color-scheme: light;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #17202a;
  background: #f4f7fb;
}

body {
  margin: 0;
}

.shell {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(340px, 0.9fr);
  gap: 24px;
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px;
}

.editor,
.preview section {
  background: #fff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 20px;
}

.preview {
  display: grid;
  gap: 16px;
  align-content: start;
}

.eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
}

h1,
h2 {
  margin: 0 0 10px;
  letter-spacing: 0;
}

.intro {
  color: #5b6776;
  line-height: 1.6;
}

fieldset {
  border: 0;
  padding: 0;
  margin: 22px 0;
}

legend {
  font-weight: 800;
  margin-bottom: 12px;
}

label {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 650;
}

input,
textarea {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #b8c4d4;
  border-radius: 6px;
  padding: 10px 12px;
  font: inherit;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.variables,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

button {
  border: 0;
  border-radius: 6px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
}

.actions button:first-child {
  background: #2563eb;
  color: white;
}

.variables button,
.actions button:last-child {
  background: #e8eef7;
  color: #17202a;
}

.watch-face {
  background: #071018;
  color: white;
  border-radius: 28px;
  min-height: 150px;
  padding: 24px;
}

#watch-title {
  font-weight: 800;
  font-size: 18px;
}

#watch-body {
  color: #d5dde8;
  line-height: 1.5;
}

.phone-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 14px;
}

.phone-card img {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  object-fit: cover;
}

pre {
  white-space: pre-wrap;
  word-break: break-all;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 6px;
  padding: 12px;
}

#status {
  min-height: 24px;
  color: #166534;
}

@media (max-width: 820px) {
  .shell {
    grid-template-columns: 1fr;
    padding: 16px;
  }

  .grid-2 {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **步骤 3：创建前端逻辑**

创建 `agent_watch/static/app.js`：

```javascript
const form = document.querySelector("#config-form");
const statusEl = document.querySelector("#status");
let activeTemplateField = null;

function formToConfig() {
  const data = new FormData(form);
  return {
    bark: {
      server: data.get("server") || "",
      key: data.get("key") || "",
      level: data.get("level") || "",
      sound: data.get("sound") || "",
      icon: data.get("icon") || ""
    },
    message: {
      title_template: data.get("title_template") || "",
      body_template: data.get("body_template") || "",
      max_body_chars: Number(data.get("max_body_chars") || 160)
    }
  };
}

function applyConfig(config) {
  form.elements.server.value = config.bark.server || "";
  form.elements.key.value = config.bark.key || "";
  form.elements.level.value = config.bark.level || "";
  form.elements.sound.value = config.bark.sound || "";
  form.elements.icon.value = config.bark.icon || "";
  form.elements.title_template.value = config.message.title_template || "";
  form.elements.body_template.value = config.message.body_template || "";
  form.elements.max_body_chars.value = config.message.max_body_chars || 160;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error((payload.errors || ["请求失败。"]).join(" "));
  }
  return payload;
}

function renderPreview(payload) {
  document.querySelector("#watch-title").textContent = payload.watch.title;
  document.querySelector("#watch-body").textContent = payload.watch.body;
  document.querySelector("#phone-title").textContent = payload.phone.title;
  document.querySelector("#phone-body").textContent = payload.phone.body;
  const icon = document.querySelector("#phone-icon");
  if (payload.phone.icon) {
    icon.src = payload.phone.icon;
    icon.hidden = false;
  } else {
    icon.hidden = true;
  }
}

async function refreshPreview() {
  const payload = await requestJson("/api/preview", {
    method: "POST",
    body: JSON.stringify(formToConfig())
  });
  renderPreview(payload);
}

async function loadInitialState() {
  const configPayload = await requestJson("/api/config");
  applyConfig(configPayload.config);
  renderPreview(await requestJson("/api/preview"));
  const install = await requestJson("/api/install-snippet");
  document.querySelector("#install-note").textContent = install.note;
  document.querySelector("#install-toml").textContent = install.toml;
  document.querySelector("#test-command").textContent = install.test_command;
}

form.addEventListener("focusin", (event) => {
  if (event.target.name === "title_template" || event.target.name === "body_template") {
    activeTemplateField = event.target;
  }
});

document.querySelectorAll("[data-var]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = activeTemplateField || form.elements.body_template;
    const value = button.dataset.var;
    const start = target.selectionStart || target.value.length;
    const end = target.selectionEnd || target.value.length;
    target.value = target.value.slice(0, start) + value + target.value.slice(end);
    target.focus();
    target.setSelectionRange(start + value.length, start + value.length);
    refreshPreview().catch((error) => statusEl.textContent = error.message);
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const saved = await requestJson("/api/config", {
      method: "POST",
      body: JSON.stringify(formToConfig())
    });
    applyConfig(saved.config);
    await refreshPreview();
    statusEl.textContent = "配置已保存。";
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

document.querySelector("#test-send").addEventListener("click", async () => {
  try {
    const payload = await requestJson("/api/test-send", {
      method: "POST",
      body: JSON.stringify(formToConfig())
    });
    statusEl.textContent = payload.message || "测试通知已发送。";
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

form.addEventListener("input", () => {
  window.clearTimeout(window.previewTimer);
  window.previewTimer = window.setTimeout(() => {
    refreshPreview().catch((error) => statusEl.textContent = error.message);
  }, 350);
});

loadInitialState().catch((error) => statusEl.textContent = error.message);
```

- [ ] **步骤 4：启动本地服务手动检查 UI**

运行：`python3 agent_watch.py serve 8765`

预期：终端输出 `Agent Watch UI: http://127.0.0.1:8765`。

在浏览器打开 `http://127.0.0.1:8765`，检查：

- 页面默认中文。
- 左侧表单和右侧预览不重叠。
- 修改模板后预览更新。
- 点击变量按钮能插入到当前模板字段。
- 安装片段显示 `notify = ["python3", ".../notify_watch.py"]`。

- [ ] **步骤 5：Commit**

```bash
git add agent_watch/static/index.html agent_watch/static/styles.css agent_watch/static/app.js
git commit -m "Add Chinese local configuration UI"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 任务 7：中文文档和最终验证

**文件：**
- 创建：`README.md`
- 修改：`codex-notify-watch.md`
- 修改：`.gitignore`

- [ ] **步骤 1：更新 README**

创建 `README.md`，必须包含：

```markdown
# Agent Watch

Agent Watch 是一个本地工具，用 Bark 把 Codex 任务完成通知推送到 iPhone，并通过系统通知同步到手表。

## 快速开始

```bash
git clone <repo-url>
cd agent-watch
python3 agent_watch.py serve
```

打开终端输出的本地地址，在页面里配置 Bark Key、消息模板和 Logo URL。

## 手动安装到 Codex

本工具不会自动修改 `~/.codex/config.toml`。请在 UI 中复制生成的 `notify = [...]` 配置片段，并手动加入你的 Codex 配置。

## 本地配置

用户配置保存在 `.agent-watch/config.json`，该目录已被 `.gitignore` 忽略。不要把 Bark Key 提交到 GitHub。
```

- [ ] **步骤 2：更新现有说明文档**

修改 `codex-notify-watch.md`：

- 保留 Bark 到 iPhone/手表链路说明。
- 更新运行方式为 `python3 agent_watch.py serve`。
- 说明 UI 会生成手动安装片段。
- 说明 `.agent-watch/config.json` 存储本地配置。

- [ ] **步骤 3：确认忽略规则**

检查 `.gitignore` 包含：

```gitignore
.agent-watch/
.omx/
.superpowers/
__pycache__/
*.pyc
.DS_Store
```

如需增加测试缓存，追加：

```gitignore
.pytest_cache/
```

- [ ] **步骤 4：运行完整测试**

运行：`python3 -m unittest discover -v`

预期：全部测试 PASS。

- [ ] **步骤 5：运行 notify 手动样例**

运行：

```bash
python3 agent_watch.py notify '{"type":"agent-turn-complete","cwd":"/tmp/agent-watch","last-assistant-message":"任务已完成。","input-messages":["测试通知"]}'
```

预期：退出码 0；未配置 Bark Key 时输出中文软失败信息，不抛异常。

- [ ] **步骤 6：运行 UI 手动样例**

运行：`python3 agent_watch.py serve 8765`

预期：

- 服务启动成功。
- 浏览器能打开 UI。
- 保存配置会创建 `.agent-watch/config.json`。
- UI 中测试发送在缺少 Bark Key 时显示中文错误。

- [ ] **步骤 7：Commit**

```bash
git add README.md codex-notify-watch.md .gitignore
git commit -m "Document Chinese Agent Watch setup"
```

提交信息需要按仓库 Lore trailer 格式补充 `Constraint:`、`Confidence:`、`Tested:`、`Co-authored-by:`。

## 最终验证

完成所有任务后运行：

```bash
python3 -m unittest discover -v
python3 agent_watch.py notify '{"type":"agent-turn-complete","cwd":"/tmp/agent-watch","last-assistant-message":"任务已完成。","input-messages":["测试通知"]}'
python3 agent_watch.py serve 8765
```

最终报告必须包含：

- 修改文件列表。
- 已实现的简化点：Python 标准库、手动安装、不托管本地 Logo、不自动改 Codex 全局配置。
- 测试结果。
- 剩余风险：真实 Bark 推送需要用户提供有效 Bark Key，手表同步仍依赖 iPhone 和手表系统设置。
