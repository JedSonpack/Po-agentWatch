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

    def test_collapse_text_preserves_plain_angle_brackets(self):
        text = collapse_text("x < y > z")
        self.assertEqual(text, "x < y > z")

    def test_collapse_text_preserves_technical_angle_brackets(self):
        text = collapse_text("命令 <npm run test> 执行失败")
        self.assertEqual(text, "命令 <npm run test> 执行失败")

    def test_collapse_text_preserves_generic_type_placeholder(self):
        text = collapse_text("接口返回 <T> 需要处理")
        self.assertEqual(text, "接口返回 <T> 需要处理")

    def test_collapse_text_preserves_inline_generic_type(self):
        text = collapse_text("类型 List<User> 已更新")
        self.assertEqual(text, "类型 List<User> 已更新")

    def test_collapse_text_preserves_uppercase_placeholder(self):
        text = collapse_text("占位符 <PATH> 未替换")
        self.assertEqual(text, "占位符 <PATH> 未替换")

    def test_collapse_text_preserves_code_review_text(self):
        text = collapse_text("命令 <code review> 执行失败")
        self.assertEqual(text, "命令 <code review> 执行失败")

    def test_collapse_text_preserves_pre_commit_text(self):
        text = collapse_text("标签 <pre commit> 需要处理")
        self.assertEqual(text, "标签 <pre commit> 需要处理")

    def test_collapse_text_preserves_div_flex_text(self):
        text = collapse_text("布局 <div flex> 被记录")
        self.assertEqual(text, "布局 <div flex> 被记录")

    def test_collapse_text_removes_html_tags_with_attributes(self):
        text = collapse_text('<span class="ok">成功</span>')
        self.assertEqual(text, "成功")

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
            ("{}", "只支持裸变量"),
            ("{project:}", "只支持裸变量"),
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

    def test_render_message_reports_stable_chinese_error_for_bad_braces(self):
        with self.assertRaises(ValueError) as ctx:
            render_message(
                SAMPLE_EVENT,
                {
                    "title_template": "{",
                    "body_template": "{summary}",
                    "max_body_chars": 80,
                },
            )

        message = str(ctx.exception)
        self.assertEqual(message, "模板格式无效：请检查花括号。")
        self.assertNotIn("Single", message)
        self.assertNotIn("encountered", message)
        self.assertNotIn("format string", message)

    def test_render_message_reports_chinese_error_for_invalid_max_body_chars(self):
        with self.assertRaises(ValueError) as ctx:
            render_message(
                SAMPLE_EVENT,
                {
                    "title_template": "{project}",
                    "body_template": "{summary}",
                    "max_body_chars": "abc",
                },
            )

        message = str(ctx.exception)
        self.assertEqual(message, "消息正文长度必须是整数。")
        self.assertNotIn("invalid literal", message)

    def test_render_message_rejects_non_string_title_template(self):
        with self.assertRaises(ValueError) as ctx:
            render_message(
                SAMPLE_EVENT,
                {
                    "title_template": None,
                    "body_template": "{summary}",
                    "max_body_chars": 80,
                },
            )

        self.assertEqual(str(ctx.exception), "标题模板必须是字符串。")

    def test_render_message_rejects_non_string_body_template(self):
        with self.assertRaises(ValueError) as ctx:
            render_message(
                SAMPLE_EVENT,
                {
                    "title_template": "{project}",
                    "body_template": None,
                    "max_body_chars": 80,
                },
            )

        self.assertEqual(str(ctx.exception), "正文模板必须是字符串。")


if __name__ == "__main__":
    unittest.main()
