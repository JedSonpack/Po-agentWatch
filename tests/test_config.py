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
        self.assertEqual(config["message"]["title_template"], "Agent 已完成：{project}")

    def test_load_config_merges_partial_user_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            path.parent.mkdir()
            path.write_text(
                json.dumps({"message": {"max_body_chars": 80}}, ensure_ascii=False),
                encoding="utf-8",
            )

            config = load_config(path)

        self.assertEqual(config["message"]["max_body_chars"], 80)
        self.assertEqual(config["bark"]["sound"], DEFAULT_CONFIG["bark"]["sound"])

    def test_load_config_returns_defaults_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            path.parent.mkdir()
            path.write_text("{invalid json", encoding="utf-8")

            config = load_config(path)

        self.assertEqual(config, DEFAULT_CONFIG)

    def test_save_config_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            config = load_config(path)
            config["bark"]["key"] = "abc123"

            save_config(config, path)

            stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["bark"]["key"], "abc123")

    def test_validate_config_rejects_invalid_max_body_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(Path(tmp) / "not-created.json")
        config["message"]["max_body_chars"] = 5

        errors = validate_config(config)

        self.assertIn("消息正文长度至少为 20 个字符。", errors)

    def test_validate_config_rejects_non_object_bark_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"bark": "oops"}, ensure_ascii=False), encoding="utf-8")

            config = load_config(path)

        errors = validate_config(config)

        self.assertIn("Bark 配置必须是对象。", errors)

    def test_validate_config_rejects_non_object_message_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".agent-watch" / "config.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"message": []}, ensure_ascii=False), encoding="utf-8")

            config = load_config(path)

        errors = validate_config(config)

        self.assertIn("消息配置必须是对象。", errors)

    def test_validate_config_rejects_non_object_root_config(self):
        errors = validate_config(None)

        self.assertIn("配置必须是对象。", errors)


if __name__ == "__main__":
    unittest.main()
