from types import SimpleNamespace
import unittest
from unittest.mock import patch

from trendradar.ai.client import AIClient


def make_response(content, finish_reason="stop", reasoning_content=None):
    message = SimpleNamespace(
        content=content,
        reasoning_content=reasoning_content,
    )
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


class AIClientTest(unittest.TestCase):
    @patch("trendradar.ai.client.completion")
    def test_retries_empty_reasoning_response_with_larger_budget(self, completion):
        completion.side_effect = [
            make_response(None, finish_reason="length", reasoning_content="思考中"),
            make_response('{"core_trends":"恢复成功"}'),
        ]
        client = AIClient(
            {
                "MODEL": "deepseek/deepseek-v4-flash",
                "API_KEY": "test-key",
                "MAX_TOKENS": 10000,
            }
        )

        result = client.chat([{"role": "user", "content": "test"}])

        self.assertEqual(result, '{"core_trends":"恢复成功"}')
        self.assertEqual(completion.call_count, 2)
        self.assertEqual(completion.call_args_list[0].kwargs["max_tokens"], 10000)
        self.assertEqual(completion.call_args_list[1].kwargs["max_tokens"], 20000)

    @patch("trendradar.ai.client.completion")
    def test_raises_diagnostic_after_empty_retry(self, completion):
        completion.side_effect = [
            make_response(None, finish_reason="length"),
            make_response(None, finish_reason="length"),
        ]
        client = AIClient(
            {
                "MODEL": "deepseek/deepseek-v4-flash",
                "API_KEY": "test-key",
                "MAX_TOKENS": 10000,
            }
        )

        with self.assertRaisesRegex(RuntimeError, "finish_reason=length"):
            client.chat([{"role": "user", "content": "test"}])

    @patch("trendradar.ai.client.completion")
    def test_extracts_text_content_blocks_without_retry(self, completion):
        completion.return_value = make_response(
            [{"type": "text", "text": "第一段"}, {"type": "text", "text": "第二段"}]
        )
        client = AIClient({"MODEL": "openai/gpt-4o-mini", "API_KEY": "test-key"})

        self.assertEqual(
            client.chat([{"role": "user", "content": "test"}]),
            "第一段\n第二段",
        )
        completion.assert_called_once()


if __name__ == "__main__":
    unittest.main()
