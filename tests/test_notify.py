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
