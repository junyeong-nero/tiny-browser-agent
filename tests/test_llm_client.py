import os
import unittest
from unittest.mock import MagicMock, patch

from llm.client import EmptyResponseError, LLMClient
from llm.provider.gemini_api import GeminiApiProvider
from llm.provider.vertex_ai import VertexAIProvider


class TestLLMClient(unittest.TestCase):
    @patch("llm.client.GeminiApiProvider.from_env")
    @patch("llm.client.VertexAIProvider.from_env")
    def test_from_env_selects_gemini_by_default(
        self, mock_vertex_provider, mock_gemini_provider
    ):
        provider = MagicMock()
        provider.name = "gemini_api"
        mock_gemini_provider.return_value = provider

        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient.from_env()

        self.assertEqual(client.provider_name, "gemini_api")
        mock_gemini_provider.assert_called_once_with()
        mock_vertex_provider.assert_not_called()

    @patch("llm.client.GeminiApiProvider.from_env")
    @patch("llm.client.VertexAIProvider.from_env")
    def test_from_env_selects_vertex_when_enabled(
        self, mock_vertex_provider, mock_gemini_provider
    ):
        provider = MagicMock()
        provider.name = "vertex_ai"
        mock_vertex_provider.return_value = provider

        with patch.dict(os.environ, {"USE_VERTEXAI": "true"}, clear=True):
            client = LLMClient.from_env()

        self.assertEqual(client.provider_name, "vertex_ai")
        mock_vertex_provider.assert_called_once_with()
        mock_gemini_provider.assert_not_called()

    def test_vertex_provider_requires_project_and_location(self):
        with patch.dict(os.environ, {"USE_VERTEXAI": "true"}, clear=True):
            with self.assertRaisesRegex(ValueError, "VERTEXAI_PROJECT"):
                VertexAIProvider.from_env()

        with patch.dict(
            os.environ,
            {"USE_VERTEXAI": "true", "VERTEXAI_PROJECT": "test-project"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "VERTEXAI_LOCATION"):
                VertexAIProvider.from_env()

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


class TestGeminiApiProvider(unittest.TestCase):
    def test_gemini_provider_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
                GeminiApiProvider.from_env()
