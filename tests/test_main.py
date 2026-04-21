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
        mock_args.highlight_mouse = True
        mock_args.headless = True
        mock_args.query = 'test_query'
        mock_args.model = 'test_model'
        mock_args.log = True
        mock_args.ui = False
        mock_args.grounding = "vision"
        mock_args.planner = False
        mock_arg_parser.return_value.parse_args.return_value = mock_args

        main.main()

        mock_playwright_browser.assert_called_once_with(
            screen_size=main.PLAYWRIGHT_SCREEN_SIZE,
            initial_url='test_url',
            highlight_mouse=True,
            headless=True,
            artifact_logger=ANY,
        )
        mock_browser_agent.assert_called_once()
        mock_browser_agent.return_value.agent_loop.assert_called_once()

    @patch("main.argparse.ArgumentParser")
    @patch("main.PlaywrightBrowser")
    @patch("main.BrowserAgent")
    def test_main_no_log(self, mock_browser_agent, mock_playwright_browser, mock_arg_parser):
        mock_args = MagicMock()
        mock_args.env = 'playwright'
        mock_args.initial_url = 'https://www.google.com'
        mock_args.highlight_mouse = False
        mock_args.headless = False
        mock_args.query = 'test_query'
        mock_args.model = 'test_model'
        mock_args.log = False
        mock_args.ui = False
        mock_args.grounding = "vision"
        mock_args.planner = False
        mock_arg_parser.return_value.parse_args.return_value = mock_args

        main.main()

        mock_playwright_browser.assert_called_once_with(
            screen_size=main.PLAYWRIGHT_SCREEN_SIZE,
            initial_url='https://www.google.com',
            highlight_mouse=False,
            headless=False,
            artifact_logger=ANY,
        )


if __name__ == '__main__':
    unittest.main()
