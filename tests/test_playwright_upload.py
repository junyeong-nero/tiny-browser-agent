import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from browser.playwright import EnvState, PlaywrightBrowser


class TestPlaywrightUploadFile(unittest.TestCase):
    def test_upload_file_rejects_paths_outside_allowed_roots(self):
        with tempfile.TemporaryDirectory() as allowed_dir, tempfile.TemporaryDirectory() as outside_dir:
            outside_file = Path(outside_dir) / "secret.txt"
            outside_file.write_text("secret", encoding="utf-8")
            browser = PlaywrightBrowser(
                screen_size=(1000, 1000),
                allowed_upload_roots=[Path(allowed_dir)],
            )
            browser._page = MagicMock()

            with self.assertRaisesRegex(PermissionError, "outside allowed upload roots"):
                browser.upload_file(10, 20, str(outside_file))

            browser._page.expect_file_chooser.assert_not_called()

    def test_upload_file_allows_paths_inside_allowed_roots(self):
        with tempfile.TemporaryDirectory() as allowed_dir:
            upload_file = Path(allowed_dir) / "upload.txt"
            upload_file.write_text("content", encoding="utf-8")
            browser = PlaywrightBrowser(
                screen_size=(1000, 1000),
                allowed_upload_roots=[Path(allowed_dir)],
            )
            browser._page = MagicMock()
            browser.current_state = MagicMock(
                return_value=EnvState(screenshot=b"png", url="https://example.com")
            )

            result = browser.upload_file(10, 20, str(upload_file))

            browser._page.mouse.click.assert_called_once_with(10, 20)
            file_chooser = browser._page.expect_file_chooser.return_value.__enter__.return_value
            file_chooser.value.set_files.assert_called_once_with(str(upload_file.resolve()))
            self.assertEqual(result.url, "https://example.com")
