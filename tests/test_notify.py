import json
import tempfile
import unittest
from pathlib import Path

from agent_watch.config import load_config, save_config
from agent_watch.notify import handle_event, load_event_from_text, normalize_event


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
        self.assertEqual(calls[0][1], "Agent 已完成：agent-watch")
        self.assertEqual(calls[0][2], "agent-watch: 完成。")

    def test_normalize_event_passthrough_codex(self):
        codex_event = {
            "type": "agent-turn-complete",
            "cwd": "/tmp/x",
            "last-assistant-message": "ok",
            "input-messages": ["hi"],
        }
        self.assertEqual(normalize_event(codex_event), codex_event)

    def test_normalize_event_translates_claude_stop_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "session.jsonl"
            # Anthropic content blocks 形式（实际 Claude transcript 的格式）
            transcript.write_text(
                json.dumps({"message": {"role": "user", "content": "请实现登录"}}, ensure_ascii=False)
                + "\n"
                + json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "登录功能已完成。"}],
                        }
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            claude_event = {
                "hook_event_name": "Stop",
                "transcript_path": str(transcript),
                "cwd": "/tmp/my-claude-project",
                "session_id": "abc",
            }

            normalized = normalize_event(claude_event)

        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["type"], "agent-turn-complete")
        self.assertEqual(normalized["cwd"], "/tmp/my-claude-project")
        self.assertEqual(normalized["last-assistant-message"], "登录功能已完成。")
        self.assertEqual(normalized["input-messages"], ["请实现登录"])

    def test_normalize_event_falls_back_when_transcript_missing(self):
        claude_event = {
            "hook_event_name": "Stop",
            "transcript_path": "/no/such/file.jsonl",
            "cwd": "/tmp/x",
        }
        normalized = normalize_event(claude_event)

        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["last-assistant-message"], "任务已完成。")
        self.assertEqual(normalized["input-messages"], [])

    def test_normalize_event_ignores_unknown_events(self):
        self.assertIsNone(normalize_event({"foo": "bar"}))
        self.assertIsNone(normalize_event({"hook_event_name": "PreToolUse"}))


if __name__ == "__main__":
    unittest.main()
