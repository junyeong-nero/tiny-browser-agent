import unittest
from unittest.mock import ANY, MagicMock, patch
import main


class TestMain(unittest.TestCase):

    @patch("main.argparse.ArgumentParser")
    @patch("main.PlaywrightBrowser")
    @patch("main.BrowserAgent")
    def test_main_playwright(self, mock_browser_agent, mock_playwright_browser, mock_arg_parser):
        mock_args = MagicMock()
        mock_args.env = 'playwright'
        mock_args.initial_url = 'test_url'
        mock_args.search_engine_url = 'search_url'
        mock_args.highlight_mouse = True
        mock_args.headless = True
        mock_args.query = 'test_query'
        mock_args.model = 'test_model'
        mock_args.log = True
        mock_args.ui = False
        mock_args.grounding = "vision"
        mock_args.planner = False
        mock_args.stealth = False
        mock_args.channel = None
        mock_args.user_agent = None
        mock_args.locale = None
        mock_args.timezone_id = None
        mock_args.proxy = None
        mock_args.storage_state = None
        mock_arg_parser.return_value.parse_args.return_value = mock_args

        main.main()

        mock_playwright_browser.assert_called_once_with(
            screen_size=main.PLAYWRIGHT_SCREEN_SIZE,
            initial_url='test_url',
            search_engine_url='search_url',
            highlight_mouse=True,
            headless=True,
            artifact_logger=ANY,
            channel=None,
            user_agent=None,
            locale=None,
            timezone_id=None,
            proxy=None,
            storage_state_path=None,
            stealth=False,
        )
        mock_browser_agent.assert_called_once()
        mock_browser_agent.return_value.agent_loop.assert_called_once()

    @patch("main.argparse.ArgumentParser")
    @patch("main.PlaywrightBrowser")
    @patch("main.PlannerAgent")
    @patch("main.BrowserAgent")
    def test_main_planner_passes_subgoals_and_replan_callback(
        self,
        mock_browser_agent,
        mock_planner_agent,
        mock_playwright_browser,
        mock_arg_parser,
    ):
        mock_args = MagicMock()
        mock_args.env = 'playwright'
        mock_args.initial_url = 'https://www.google.com'
        mock_args.search_engine_url = 'https://duckduckgo.com'
        mock_args.highlight_mouse = False
        mock_args.headless = False
        mock_args.query = 'test_query'
        mock_args.model = 'test_model'
        mock_args.log = False
        mock_args.ui = False
        mock_args.grounding = "vision"
        mock_args.planner = True
        mock_args.stealth = False
        mock_args.channel = None
        mock_args.user_agent = None
        mock_args.locale = None
        mock_args.timezone_id = None
        mock_args.proxy = None
        mock_args.storage_state = None
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        subgoals = [MagicMock()]
        mock_planner_agent.return_value.plan.return_value = subgoals

        main.main()

        mock_planner_agent.assert_called_once_with(query='test_query')
        call_kwargs = mock_browser_agent.call_args.kwargs
        self.assertIs(call_kwargs["subgoals"], subgoals)
        self.assertIs(call_kwargs["replan_callback"], mock_planner_agent.return_value.replan)
        self.assertEqual(call_kwargs["max_steps_per_subgoal"], main.app_config.max_steps_per_subgoal())
        self.assertEqual(call_kwargs["max_total_steps"], main.app_config.max_total_steps())
        self.assertEqual(call_kwargs["max_subgoals"], main.app_config.max_subgoals())

    @patch("main.argparse.ArgumentParser")
    @patch("main.PlaywrightBrowser")
    @patch("main.PlannerAgent")
    @patch("main.BrowserAgent")
    def test_main_planner_empty_plan_falls_back_to_actor_loop(
        self,
        mock_browser_agent,
        mock_planner_agent,
        mock_playwright_browser,
        mock_arg_parser,
    ):
        mock_args = MagicMock()
        mock_args.env = 'playwright'
        mock_args.initial_url = 'https://www.google.com'
        mock_args.search_engine_url = 'https://duckduckgo.com'
        mock_args.highlight_mouse = False
        mock_args.headless = False
        mock_args.query = 'test_query'
        mock_args.model = 'test_model'
        mock_args.log = False
        mock_args.ui = False
        mock_args.grounding = "vision"
        mock_args.planner = True
        mock_args.stealth = False
        mock_args.channel = None
        mock_args.user_agent = None
        mock_args.locale = None
        mock_args.timezone_id = None
        mock_args.proxy = None
        mock_args.storage_state = None
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        mock_planner_agent.return_value.plan.return_value = []

        with patch("main.emit") as mock_emit:
            main.main()

        call_kwargs = mock_browser_agent.call_args.kwargs
        self.assertIsNone(call_kwargs["subgoals"])
        self.assertIsNone(call_kwargs["replan_callback"])
        mock_browser_agent.return_value.agent_loop.assert_called_once()
        mock_emit.assert_any_call(
            {"type": "planner_fallback", "reason": "no valid subgoals returned"}
        )

    @patch("main.argparse.ArgumentParser")
    @patch("main.PlaywrightBrowser")
    @patch("main.BrowserAgent")
    def test_main_no_log(self, mock_browser_agent, mock_playwright_browser, mock_arg_parser):
        mock_args = MagicMock()
        mock_args.env = 'playwright'
        mock_args.initial_url = 'https://www.google.com'
        mock_args.search_engine_url = 'https://duckduckgo.com'
        mock_args.highlight_mouse = False
        mock_args.headless = False
        mock_args.query = 'test_query'
        mock_args.model = 'test_model'
        mock_args.log = False
        mock_args.ui = False
        mock_args.grounding = "vision"
        mock_args.planner = False
        mock_args.stealth = False
        mock_args.channel = None
        mock_args.user_agent = None
        mock_args.locale = None
        mock_args.timezone_id = None
        mock_args.proxy = None
        mock_args.storage_state = None
        mock_arg_parser.return_value.parse_args.return_value = mock_args

        main.main()

        mock_playwright_browser.assert_called_once_with(
            screen_size=main.PLAYWRIGHT_SCREEN_SIZE,
            initial_url='https://www.google.com',
            search_engine_url='https://duckduckgo.com',
            highlight_mouse=False,
            headless=False,
            artifact_logger=ANY,
            channel=None,
            user_agent=None,
            locale=None,
            timezone_id=None,
            proxy=None,
            storage_state_path=None,
            stealth=False,
        )


if __name__ == '__main__':
    unittest.main()
