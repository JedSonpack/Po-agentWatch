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

    def test_collapse_text_removes_unclosed_code_block(self):
        text = collapse_text("结果如下：```python\nsecret = 1\nprint(secret)")
        self.assertNotIn("secret", text)
        self.assertNotIn("print(secret)", text)
        self.assertIn("代码省略", text)

    def test_shorten_prefers_sentence_boundary(self):
        result = shorten("第一句很重要。第二句会被截断，因为内容太长。", 10)
        self.assertEqual(result, "第一句很重要。...")

    def test_shorten_never_exceeds_budget_after_ellipsis(self):
        result = shorten("abcdefghijk", 10)
        self.assertLessEqual(len(result), 10)
        self.assertTrue(result.endswith("..."))

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

    def test_render_message_rejects_invalid_template_syntax(self):
        cases = [
            ("{", "模板格式无效"),
            ("{}", "只支持裸变量"),
            ("{project!r}", "只支持裸变量"),
            ("{project:>10}", "只支持裸变量"),
            ("{project:{time}}", "只支持裸变量"),
        ]

        for template, expected_message in cases:
            with self.subTest(template=template):
                with self.assertRaises(ValueError) as ctx:
                    render_message(
                        SAMPLE_EVENT,
                        {
                            "title_template": template,
                            "body_template": "{summary}",
                            "max_body_chars": 80,
                        },
                    )
                self.assertIn(expected_message, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
