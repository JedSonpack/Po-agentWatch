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
