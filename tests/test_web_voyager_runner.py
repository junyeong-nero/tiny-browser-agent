import argparse
import unittest
from unittest import mock

from scripts import batch_runner as runner


class WebVoyagerRunnerTest(unittest.TestCase):
    def test_korean_online_mind2web_defaults_to_train_task(self):
        args = runner.parse_args(["--dataset", "junyeong-nero/korean-online-mind2web"])

        self.assertEqual(args.config, "default")
        self.assertEqual(args.split, "train")
        self.assertEqual(args.task_field, "task")

    def test_parse_args_accepts_level_filter(self):
        args = runner.parse_args(["--level", "hard", "--level", "medium"])

        self.assertEqual(args.level, ["hard", "medium"])

    def test_fetch_tasks_filters_by_level_across_pages(self):
        pages = [
            {
                "rows": [
                    {"row_idx": 0, "row": {"id": "easy-0", "task": "easy task", "level": "easy"}},
                    {"row_idx": 1, "row": {"id": "hard-1", "task": "hard task 1", "level": "hard"}},
                ]
            },
            {
                "rows": [
                    {"row_idx": 2, "row": {"id": "medium-2", "task": "medium task", "level": "medium"}},
                    {"row_idx": 3, "row": {"id": "hard-3", "task": "hard task 2", "level": "Hard"}},
                ]
            },
        ]

        def fake_request_rows(**kwargs):
            return pages[0] if kwargs["offset"] == 0 else pages[1]

        with mock.patch.object(runner, "MAX_PAGE_SIZE", 2), mock.patch.object(
            runner, "_request_rows", side_effect=fake_request_rows
        ) as request_rows:
            tasks = runner.fetch_tasks(
                dataset="junyeong-nero/korean-online-mind2web",
                config="default",
                split="train",
                offset=0,
                limit=2,
                task_field="task",
                levels=["hard"],
            )

        self.assertEqual([task.task_id for task in tasks], ["hard-1", "hard-3"])
        self.assertEqual(request_rows.call_count, 2)

    def test_fetch_tasks_filters_level_from_metadata(self):
        payload = {
            "rows": [
                {
                    "row_idx": 4,
                    "row": {
                        "id": "metadata-hard",
                        "task": "metadata task",
                        "metadata": '{"level": "hard", "website": "example.com"}',
                    },
                }
            ]
        }
        with mock.patch.object(runner, "_request_rows", return_value=payload):
            tasks = runner.fetch_tasks(
                dataset="dataset",
                config="default",
                split="train",
                offset=4,
                limit=1,
                task_field="task",
                levels=["hard"],
            )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "metadata-hard")
        self.assertEqual(tasks[0].metadata["level"], "hard")

    def test_fetch_tasks_keeps_korean_id_and_initial_url(self):
        payload = {
            "rows": [
                {
                    "row_idx": 0,
                    "row": {
                        "task_id": "kr-yogiyo-015",
                        "website": "yogiyo.co.kr",
                        "domain": "food-delivery",
                        "task": "요기요에서 초밥 전문점을 찾아줘.",
                        "task_en": "Find a sushi restaurant on Yogiyo.",
                        "level": "hard",
                        "url": "https://www.yogiyo.co.kr",
                    },
                }
            ]
        }
        with mock.patch.object(runner, "_request_rows", return_value=payload):
            tasks = runner.fetch_tasks(
                dataset="junyeong-nero/korean-online-mind2web",
                config="default",
                split="train",
                offset=0,
                limit=1,
                task_field="task",
            )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task, "요기요에서 초밥 전문점을 찾아줘.")
        self.assertEqual(tasks[0].task_id, "kr-yogiyo-015")
        self.assertEqual(tasks[0].initial_url, "https://www.yogiyo.co.kr")
        self.assertEqual(tasks[0].metadata["domain"], "food-delivery")
        self.assertEqual(tasks[0].metadata["task_en"], "Find a sushi restaurant on Yogiyo.")

    def test_auto_task_field_supports_online_mind2web_prompt(self):
        payload = {
            "rows": [
                {
                    "row_idx": 12,
                    "row": {
                        "id": "mind2web_012",
                        "prompt": "Browse used Audi cars made before 2015 and sort by lowest price on KBB.",
                        "metadata": '{"website": "https://www.kbb.com/"}',
                    },
                }
            ]
        }
        with mock.patch.object(runner, "_request_rows", return_value=payload):
            tasks = runner.fetch_tasks(
                dataset="Genteki/Online-Mind2Web",
                config="default",
                split="train",
                offset=12,
                limit=1,
                task_field="auto",
            )

        self.assertEqual(tasks[0].task_id, "mind2web_012")
        self.assertEqual(tasks[0].initial_url, "https://www.kbb.com/")
        self.assertEqual(tasks[0].task, "Browse used Audi cars made before 2015 and sort by lowest price on KBB.")

    def test_build_command_uses_normalized_initial_url(self):
        args = argparse.Namespace(
            headless="True",
            grounding=None,
            model=None,
            log_agent=False,
            video_agent=False,
            metadata_initial_url=True,
            extra_arg=[],
        )
        task = runner.TaskRow(index=1, task="태스크", metadata={"task_id": "kr", "website": "naver.com"})

        self.assertEqual(
            runner.build_command(args, task),
            ["uv", "run", "main.py", "--planner", "--headless", "True", "--initial_url", "https://naver.com", "태스크"],
        )

    def test_build_command_can_forward_video_flag(self):
        args = argparse.Namespace(
            headless="True",
            grounding=None,
            model=None,
            log_agent=True,
            video_agent=True,
            metadata_initial_url=False,
            extra_arg=[],
        )
        task = runner.TaskRow(index=1, task="태스크", metadata={})

        self.assertEqual(
            runner.build_command(args, task),
            ["uv", "run", "main.py", "--planner", "--headless", "True", "--log", "--video", "태스크"],
        )


if __name__ == "__main__":
    unittest.main()
