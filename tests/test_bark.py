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
