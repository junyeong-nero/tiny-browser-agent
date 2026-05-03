import os
import unittest
from unittest.mock import MagicMock, patch

from llm.client import EmptyResponseError, LLMClient
from llm.provider.gemini_api import GeminiProvider


class TestLLMClient(unittest.TestCase):
    @patch("llm.client.GeminiProvider.from_env")
    def test_from_env_uses_gemini(self, mock_gemini_provider):
        provider = MagicMock()
        provider.name = "gemini_api"
        mock_gemini_provider.return_value = provider

        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient.from_env()

        self.assertEqual(client.provider_name, "gemini_api")
        mock_gemini_provider.assert_called_once_with()

    @patch("llm.client.time.sleep")
    def test_generate_content_retries_on_empty_response(self, mock_sleep):
        provider = MagicMock()
        provider.name = "gemini_api"
        empty_response = MagicMock(candidates=[])
        success_response = MagicMock(candidates=[MagicMock()])
        provider.generate_content.side_effect = [empty_response, success_response]
        client = LLMClient(provider=provider, max_retries=3, base_delay_s=1)

        response = client.generate_content(
            model="test-model",
            contents=[],
            config=MagicMock(),
        )

        self.assertIs(response, success_response)
        self.assertEqual(provider.generate_content.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("llm.client.time.sleep")
    def test_generate_content_raises_after_persistent_empty_responses(self, mock_sleep):
        provider = MagicMock()
        provider.name = "gemini_api"
        provider.generate_content.return_value = MagicMock(candidates=[])
        client = LLMClient(provider=provider, max_retries=3, base_delay_s=1)

        with self.assertRaises(EmptyResponseError):
            client.generate_content(
                model="test-model",
                contents=[],
                config=MagicMock(),
            )

        self.assertEqual(provider.generate_content.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("llm.client.time.sleep")
    def test_generate_content_retries_transport_errors(self, mock_sleep):
        provider = MagicMock()
        provider.name = "gemini_api"
        success_response = MagicMock(candidates=[MagicMock()])
        provider.generate_content.side_effect = [RuntimeError("boom"), success_response]
        client = LLMClient(provider=provider, max_retries=3, base_delay_s=1)

        response = client.generate_content(
            model="test-model",
            contents=[],
            config=MagicMock(),
        )

        self.assertIs(response, success_response)
        self.assertEqual(provider.generate_content.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("llm.client.GeminiProvider.from_env")
    def test_from_provider_name_uses_gemini_text(self, mock_provider_from_env):
        provider = MagicMock()
        provider.name = "gemini_text"
        mock_provider_from_env.return_value = provider

        client = LLMClient.from_provider_name("gemini_text")

        self.assertEqual(client.provider_name, "gemini_text")
        mock_provider_from_env.assert_called_once_with(name="gemini_text")

    @patch("llm.client.GeminiProvider.from_env")
    def test_from_provider_name_uses_gemini_computer_use(self, mock_provider_from_env):
        provider = MagicMock()
        provider.name = "gemini_computer_use"
        mock_provider_from_env.return_value = provider

        client = LLMClient.from_provider_name("gemini_computer_use")

        self.assertEqual(client.provider_name, "gemini_computer_use")
        mock_provider_from_env.assert_called_once_with(name="gemini_computer_use")

    @patch("llm.client.NvidiaProvider.from_env")
    def test_from_provider_name_uses_nvidia(self, mock_provider_from_env):
        provider = MagicMock()
        provider.name = "nvidia"
        mock_provider_from_env.return_value = provider

        client = LLMClient.from_provider_name("nvidia")

        self.assertEqual(client.provider_name, "nvidia")
        mock_provider_from_env.assert_called_once_with()

    @patch("llm.client.OpenAIProvider.from_env")
    def test_from_provider_name_uses_openai(self, mock_provider_from_env):
        provider = MagicMock()
        provider.name = "openai"
        mock_provider_from_env.return_value = provider

        client = LLMClient.from_provider_name("openai")

        self.assertEqual(client.provider_name, "openai")
        mock_provider_from_env.assert_called_once_with()

    @patch("llm.client.OpenRouterProvider.from_env")
    def test_from_provider_name_uses_openrouter(self, mock_provider_from_env):
        provider = MagicMock()
        provider.name = "openrouter"
        mock_provider_from_env.return_value = provider

        client = LLMClient.from_provider_name("openrouter")

        self.assertEqual(client.provider_name, "openrouter")
        mock_provider_from_env.assert_called_once_with()

    def test_from_provider_name_rejects_unsupported_provider(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider 'unknown'"):
            LLMClient.from_provider_name("unknown")


class TestGeminiProvider(unittest.TestCase):
    def test_gemini_provider_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
                GeminiProvider.from_env()


class TestNvidiaProvider(unittest.TestCase):
    def test_nvidia_provider_requires_api_key(self):
        from llm.provider.nvidia import NvidiaProvider

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "NVIDIA_API_KEY"):
                NvidiaProvider.from_env()

    def test_nvidia_provider_from_env_uses_shared_timeout_and_flags(self):
        from llm.provider.nvidia import NvidiaProvider

        with patch.dict(
            os.environ,
            {
                "NVIDIA_API_KEY": "nvidia-key",
                "NVIDIA_BASE_URL": "https://integrate.test/v1",
                "NVIDIA_THINKING": "off",
                "NVIDIA_REASONING_EFFORT": "medium",
                "ACTION_SUMMARY_TIMEOUT_SECONDS": "7.5",
            },
            clear=True,
        ):
            provider = NvidiaProvider.from_env()

        self.assertEqual(provider._chat_completions_url, "https://integrate.test/v1/chat/completions")
        self.assertEqual(provider._timeout_seconds, 7.5)
        self.assertEqual(
            provider._extra_body,
            {"chat_template_kwargs": {"thinking": False, "reasoning_effort": "medium"}},
        )


class TestChatCompletionProviderEnvBootstrap(unittest.TestCase):
    def test_openai_provider_from_env_uses_timeout_and_base_url(self):
        from llm.provider.openai import OpenAIProvider

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_BASE_URL": "https://openai.test/v1",
                "ACTION_SUMMARY_TIMEOUT_SECONDS": "8.5",
            },
            clear=True,
        ):
            provider = OpenAIProvider.from_env()

        self.assertEqual(provider._chat_completions_url, "https://openai.test/v1/chat/completions")
        self.assertEqual(provider._timeout_seconds, 8.5)

    def test_openrouter_provider_from_env_uses_optional_headers(self):
        from llm.provider.openrouter import OpenRouterProvider

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "router-key",
                "OPENROUTER_BASE_URL": "https://router.test/v1",
                "OPENROUTER_HTTP_REFERER": "https://app.test",
                "OPENROUTER_TITLE": "Tiny Browser Agent",
                "ACTION_SUMMARY_TIMEOUT_SECONDS": "9",
            },
            clear=True,
        ):
            provider = OpenRouterProvider.from_env()

        self.assertEqual(provider._chat_completions_url, "https://router.test/v1/chat/completions")
        self.assertEqual(provider._timeout_seconds, 9.0)
        self.assertEqual(provider._http_referer, "https://app.test")
        self.assertEqual(provider._title, "Tiny Browser Agent")

    def test_provider_from_env_rejects_invalid_timeout(self):
        from llm.provider.openai import OpenAIProvider

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "ACTION_SUMMARY_TIMEOUT_SECONDS": "not-a-number",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "ACTION_SUMMARY_TIMEOUT_SECONDS"):
                OpenAIProvider.from_env()

class _FakeHTTPResponse:
    def __init__(self, payload: str):
        self._payload = payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


class TestChatCompletionsProviders(unittest.TestCase):
    @patch("llm.provider.chat_completion_http.request.urlopen")
    @patch("llm.provider.chat_completion_http.ChatCompletionsProvider._build_ssl_context", return_value=None)
    def test_openai_generate_text_posts_chat_completion_payload(self, _mock_ssl, mock_urlopen):
        from llm.provider.openai import OpenAIProvider

        mock_urlopen.return_value = _FakeHTTPResponse(
            '{"choices":[{"message":{"content":"  hello  "}}]}'
        )
        provider = OpenAIProvider(api_key="key", base_url="https://example.test/v1", timeout_seconds=3)

        text = provider.generate_text(
            model="model-a",
            prompt="user prompt",
            system_prompt="system prompt",
            max_tokens=42,
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        self.assertEqual(text, "hello")
        http_request = mock_urlopen.call_args.args[0]
        body = __import__("json").loads(http_request.data.decode("utf-8"))
        self.assertEqual(http_request.full_url, "https://example.test/v1/chat/completions")
        self.assertEqual(http_request.headers["Authorization"], "Bearer key")
        self.assertEqual(body["model"], "model-a")
        self.assertEqual(
            body["messages"],
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
        )
        self.assertEqual(body["max_completion_tokens"], 42)
        self.assertNotIn("max_tokens", body)
        self.assertEqual(body["temperature"], 0.5)
        self.assertEqual(body["response_format"], {"type": "json_object"})

    @patch("llm.provider.chat_completion_http.request.urlopen")
    @patch("llm.provider.chat_completion_http.ChatCompletionsProvider._build_ssl_context", return_value=None)
    def test_openai_generate_content_uses_max_completion_tokens(self, _mock_ssl, mock_urlopen):
        from google.genai import types

        from llm.provider.openai import OpenAIProvider

        mock_urlopen.return_value = _FakeHTTPResponse(
            '{"choices":[{"message":{"content":"answer"}}]}'
        )
        provider = OpenAIProvider(
            api_key="key",
            base_url="https://example.test/v1",
            timeout_seconds=3,
        )

        provider.generate_content(
            model="gpt-5-mini",
            contents=[types.Content(role="user", parts=[types.Part(text="hello")])],
            config=types.GenerateContentConfig(max_output_tokens=123),
        )

        http_request = mock_urlopen.call_args.args[0]
        body = __import__("json").loads(http_request.data.decode("utf-8"))
        self.assertEqual(body["max_completion_tokens"], 123)
        self.assertNotIn("max_tokens", body)

    @patch("llm.provider.chat_completion_http.request.urlopen")
    @patch("llm.provider.chat_completion_http.ChatCompletionsProvider._build_ssl_context", return_value=None)
    def test_openrouter_generate_text_includes_optional_headers(self, _mock_ssl, mock_urlopen):
        from llm.provider.openrouter import OpenRouterProvider

        mock_urlopen.return_value = _FakeHTTPResponse(
            '{"choices":[{"message":{"content":[{"type":"text","text":"part one"},{"type":"text","text":"part two"}]}}]}'
        )
        provider = OpenRouterProvider(
            api_key="router-key",
            base_url="https://router.test/api/v1/",
            http_referer="https://app.test",
            title="Tiny Browser Agent",
        )

        text = provider.generate_text(model="router-model", prompt="hello")

        self.assertEqual(text, "part one\npart two")
        http_request = mock_urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "https://router.test/api/v1/chat/completions")
        self.assertEqual(http_request.headers["Authorization"], "Bearer router-key")
        self.assertEqual(http_request.headers["Http-referer"], "https://app.test")
        self.assertEqual(http_request.headers["X-title"], "Tiny Browser Agent")

    @patch("llm.provider.chat_completion_http.request.urlopen")
    @patch("llm.provider.chat_completion_http.ChatCompletionsProvider._build_ssl_context", return_value=None)
    def test_nvidia_generate_content_includes_thinking_extra_body(self, _mock_ssl, mock_urlopen):
        from google.genai import types

        from llm.provider.nvidia import NvidiaProvider

        mock_urlopen.return_value = _FakeHTTPResponse(
            '{"choices":[{"message":{"reasoning_content":"think","content":"answer"}}]}'
        )
        provider = NvidiaProvider(
            api_key="nvidia-key",
            base_url="https://integrate.test/v1",
            reasoning_effort="high",
            timeout_seconds=3,
        )

        response = provider.generate_content(
            model="deepseek-ai/deepseek-v4-flash",
            contents=[types.Content(role="user", parts=[types.Part(text="hello")])],
            config=types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                max_output_tokens=16384,
            ),
        )

        http_request = mock_urlopen.call_args.args[0]
        body = __import__("json").loads(http_request.data.decode("utf-8"))
        self.assertEqual(http_request.full_url, "https://integrate.test/v1/chat/completions")
        self.assertEqual(http_request.headers["Authorization"], "Bearer nvidia-key")
        self.assertEqual(body["model"], "deepseek-ai/deepseek-v4-flash")
        self.assertEqual(body["temperature"], 1)
        self.assertEqual(body["top_p"], 0.95)
        self.assertEqual(body["max_tokens"], 16384)
        self.assertEqual(
            body["chat_template_kwargs"],
            {"thinking": True, "reasoning_effort": "high"},
        )

        parts = response.candidates[0].content.parts
        self.assertEqual(parts[0].text, "think")
        self.assertTrue(parts[0].thought)
        self.assertEqual(parts[1].text, "answer")
