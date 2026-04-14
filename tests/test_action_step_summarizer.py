import json
import os
import unittest
from unittest.mock import patch

from google.genai import types

from action_review import ActionReviewService
from action_step_summarizer import ActionStepSummary, ActionStepSummarizer
from llm.provider.openai import OpenAIProvider
from llm.provider.openrouter import OpenRouterProvider


class TestOpenRouterProvider(unittest.TestCase):
    def test_openrouter_provider_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
                OpenRouterProvider.from_env()

    @patch("llm.provider.openrouter.request.urlopen")
    def test_generate_text_builds_chat_completion_request(self, mock_urlopen):
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": '{"action_summary":"검색창 클릭","reason":"검색어를 입력하려고 했습니다."}',
                    }
                }
            ]
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            response_payload
        ).encode("utf-8")

        provider = OpenRouterProvider(api_key="test-key", timeout_seconds=3)
        text = provider.generate_text(
            model="gpt-4o-mini",
            system_prompt="system",
            prompt="prompt",
            max_tokens=64,
            temperature=0,
            response_format={"type": "json_object"},
        )

        self.assertEqual(
            text,
            '{"action_summary":"검색창 클릭","reason":"검색어를 입력하려고 했습니다."}',
        )
        http_request = mock_urlopen.call_args.args[0]
        request_body = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(request_body["model"], "gpt-4o-mini")
        self.assertEqual(request_body["messages"][0], {"role": "system", "content": "system"})
        self.assertEqual(request_body["messages"][1], {"role": "user", "content": "prompt"})
        self.assertEqual(request_body["response_format"], {"type": "json_object"})


class TestOpenAIProvider(unittest.TestCase):
    def test_openai_provider_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                OpenAIProvider.from_env()

    @patch("llm.provider.openai.request.urlopen")
    def test_generate_text_builds_chat_completion_request(self, mock_urlopen):
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": '{"action_summary":"검색창 클릭","reason":"검색어를 입력하려고 했습니다."}',
                    }
                }
            ]
        }
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            response_payload
        ).encode("utf-8")

        provider = OpenAIProvider(api_key="test-key", timeout_seconds=3)
        text = provider.generate_text(
            model="gpt-4o-mini",
            system_prompt="system",
            prompt="prompt",
            max_tokens=64,
            temperature=0,
            response_format={"type": "json_schema", "json_schema": {"name": "summary", "schema": {}}},
        )

        self.assertEqual(
            text,
            '{"action_summary":"검색창 클릭","reason":"검색어를 입력하려고 했습니다."}',
        )
        http_request = mock_urlopen.call_args.args[0]
        request_body = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(request_body["model"], "gpt-4o-mini")
        self.assertEqual(request_body["messages"][0], {"role": "system", "content": "system"})
        self.assertEqual(request_body["messages"][1], {"role": "user", "content": "prompt"})
        self.assertEqual(
            request_body["response_format"],
            {"type": "json_schema", "json_schema": {"name": "summary", "schema": {}}},
        )


class _FakeStepSummarizer:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def summarize_action(self, **kwargs) -> ActionStepSummary | None:
        self.calls.append(kwargs)
        return ActionStepSummary(
            action_summary="예시 페이지 열기",
            reason="요청한 페이지로 이동하기 위한 단계였습니다.",
            summary_source="openrouter",
        )


class _FailingStepSummarizer:
    def summarize_action(self, **kwargs) -> ActionStepSummary | None:
        del kwargs
        return None


class TestActionReviewServiceSummarizer(unittest.TestCase):
    def test_build_review_and_persisted_metadata_use_step_summarizer_once(self):
        summarizer = _FakeStepSummarizer()
        review_service = ActionReviewService(
            query="예시 페이지로 이동해줘",
            step_summarizer=summarizer,
        )
        function_call = types.FunctionCall(
            name="navigate",
            args={"url": "https://example.com"},
        )

        review_metadata = review_service.build_review_metadata_for_action(
            step_id=1,
            function_call_index=1,
            function_call=function_call,
            reasoning="Open the example page first.",
            artifacts={"url": "https://example.com"},
        )
        persisted_metadata = review_service.build_persisted_action_metadata(
            step_id=1,
            function_call_index=1,
            function_call=function_call,
            reasoning="Open the example page first.",
            artifacts={"url": "https://example.com"},
        )

        self.assertEqual(review_metadata["user_visible_label"], "예시 페이지 열기")
        self.assertEqual(persisted_metadata["action_summary"], "예시 페이지 열기")
        self.assertEqual(
            persisted_metadata["reason"],
            "요청한 페이지로 이동하기 위한 단계였습니다.",
        )
        self.assertEqual(persisted_metadata["summary_source"], "openrouter")
        self.assertEqual(len(summarizer.calls), 1)

    def test_build_persisted_metadata_falls_back_when_summarizer_is_unavailable(self):
        review_service = ActionReviewService(
            query="예시 페이지로 이동해줘",
            step_summarizer=_FailingStepSummarizer(),
        )
        function_call = types.FunctionCall(
            name="navigate",
            args={"url": "https://example.com"},
        )

        persisted_metadata = review_service.build_persisted_action_metadata(
            step_id=1,
            function_call_index=1,
            function_call=function_call,
            reasoning=None,
            artifacts={"url": "https://example.com"},
        )

        self.assertEqual(
            persisted_metadata["action_summary"],
            "Navigated to https://example.com",
        )
        self.assertEqual(
            persisted_metadata["reason"],
            "Needed to open https://example.com.",
        )
        self.assertEqual(persisted_metadata["summary_source"], "app_derived")


class TestActionStepSummarizer(unittest.TestCase):
    @patch("action_step_summarizer.OpenAIProvider.from_env")
    @patch("action_step_summarizer.OpenRouterProvider.from_env")
    def test_from_env_returns_none_when_disabled(
        self,
        mock_openrouter_provider_from_env,
        mock_openai_provider_from_env,
    ):
        with patch.dict(os.environ, {}, clear=True):
            summarizer = ActionStepSummarizer.from_env()

        self.assertIsNone(summarizer)
        mock_openrouter_provider_from_env.assert_not_called()
        mock_openai_provider_from_env.assert_not_called()

    @patch("action_step_summarizer.OpenAIProvider.from_env")
    @patch("action_step_summarizer.OpenRouterProvider.from_env")
    def test_from_env_requires_supported_provider(
        self,
        mock_openrouter_provider_from_env,
        mock_openai_provider_from_env,
    ):
        with patch.dict(
            os.environ,
            {"ACTION_SUMMARY_PROVIDER": "unsupported"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported ACTION_SUMMARY_PROVIDER"):
                ActionStepSummarizer.from_env()

        mock_openrouter_provider_from_env.assert_not_called()
        mock_openai_provider_from_env.assert_not_called()

    @patch("action_step_summarizer.OpenAIProvider.from_env")
    def test_from_env_uses_openai_provider(self, mock_provider_from_env):
        provider = object()
        mock_provider_from_env.return_value = provider

        with patch.dict(
            os.environ,
            {
                "ACTION_SUMMARY_PROVIDER": "openai",
                "ACTION_SUMMARY_MODEL": "gpt-4o-mini",
            },
            clear=True,
        ):
            summarizer = ActionStepSummarizer.from_env()

        if summarizer is None:
            self.fail("Expected ActionStepSummarizer.from_env() to return a summarizer")
        self.assertIs(summarizer._provider, provider)
        self.assertEqual(summarizer._model, "gpt-4o-mini")
        mock_provider_from_env.assert_called_once_with()

    @patch("action_step_summarizer.OpenAIProvider.from_env")
    @patch("action_step_summarizer.OpenRouterProvider.from_env")
    def test_from_env_infers_openai_provider_from_api_key(
        self,
        mock_openrouter_provider_from_env,
        mock_openai_provider_from_env,
    ):
        provider = object()
        mock_openai_provider_from_env.return_value = provider

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
            },
            clear=True,
        ):
            summarizer = ActionStepSummarizer.from_env()

        if summarizer is None:
            self.fail("Expected ActionStepSummarizer.from_env() to infer OpenAI from OPENAI_API_KEY")
        self.assertIs(summarizer._provider, provider)
        self.assertEqual(summarizer._model, "gpt-4o-mini")
        self.assertEqual(summarizer._summary_source, "openai")
        mock_openai_provider_from_env.assert_called_once_with()
        mock_openrouter_provider_from_env.assert_not_called()

    @patch("action_step_summarizer.OpenAIProvider.from_env")
    @patch("action_step_summarizer.OpenRouterProvider.from_env")
    def test_from_env_infers_openrouter_provider_from_api_key(
        self,
        mock_openrouter_provider_from_env,
        mock_openai_provider_from_env,
    ):
        provider = object()
        mock_openrouter_provider_from_env.return_value = provider

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
            },
            clear=True,
        ):
            summarizer = ActionStepSummarizer.from_env()

        if summarizer is None:
            self.fail("Expected ActionStepSummarizer.from_env() to infer OpenRouter from OPENROUTER_API_KEY")
        self.assertIs(summarizer._provider, provider)
        self.assertEqual(summarizer._model, "gpt-4o-mini")
        self.assertEqual(summarizer._summary_source, "openrouter")
        mock_openrouter_provider_from_env.assert_called_once_with()
        mock_openai_provider_from_env.assert_not_called()
