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

    def test_build_install_snippet_test_command_uses_sample_event(self):
        """测试命令必须用 SAMPLE_EVENT 序列化生成，保证「预览看到什么、命令跑出来就是什么」。"""
        from agent_watch.server import SAMPLE_EVENT

        snippet = build_install_snippet(Path("/repo/notify_watch.py"))
        # 预览里展示的关键字段必须出现在测试命令里
        self.assertIn(SAMPLE_EVENT["last-assistant-message"], snippet["test_command"])
        self.assertIn(SAMPLE_EVENT["cwd"], snippet["test_command"])
        self.assertIn(SAMPLE_EVENT["input-messages"][0], snippet["test_command"])

    def test_build_install_snippet_includes_codex_and_claude(self):
        """安装片段应同时给 Codex 和 Claude Code 两套接入说明。"""
        snippet = build_install_snippet(Path("/repo/notify_watch.py"))
        agents = snippet.get("agents")
        self.assertIsInstance(agents, list)
        ids = {a["id"] for a in agents}
        self.assertEqual(ids, {"codex", "claude"})
        codex = next(a for a in agents if a["id"] == "codex")
        claude = next(a for a in agents if a["id"] == "claude")
        # Codex 用 toml，Claude 用 json hooks
        self.assertIn('notify = ["python3"', codex["step1_code"])
        self.assertIn('"hooks"', claude["step1_code"])
        self.assertIn('"Stop"', claude["step1_code"])
        # Claude 测试命令应该用 stdin 管道，不是 argv
        self.assertIn("|", claude["step2_code"])
        self.assertIn("hook_event_name", claude["step2_code"])


if __name__ == "__main__":
    unittest.main()
