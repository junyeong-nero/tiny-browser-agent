import json
from pathlib import Path
from typing import Any

from google.genai import types

from action_review import ActionReviewService, AmbiguityCandidate


class ActionMetadataWriter:
    def __init__(self, browser_computer: Any, review_service: ActionReviewService):
        self._browser_computer = browser_computer
        self._review_service = review_service

    def resolve_metadata_file_path(
        self,
        artifacts: dict[str, Any] | None,
    ) -> Path | None:
        if not artifacts:
            return None

        metadata_path_value = artifacts.get("metadata_path")
        if not isinstance(metadata_path_value, str) or not metadata_path_value:
            return None

        metadata_path = Path(metadata_path_value)
        if metadata_path.is_absolute():
            return metadata_path

        history_dir_getter = getattr(self._browser_computer, "history_dir", None)
        if not callable(history_dir_getter):
            return None

        history_dir = history_dir_getter()
        if history_dir is None:
            return None
        if not isinstance(history_dir, (str, Path)):
            return None

        return Path(history_dir) / metadata_path

    def enrich_persisted_action_metadata(
        self,
        step_id: int,
        function_call_index: int,
        function_call: types.FunctionCall,
        reasoning: str | None,
        artifacts: dict[str, Any] | None,
        ambiguity_candidate: AmbiguityCandidate | None,
    ) -> None:
        metadata_file_path = self.resolve_metadata_file_path(artifacts)
        if metadata_file_path is None or not metadata_file_path.exists():
            return

        try:
            existing_metadata = json.loads(metadata_file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(existing_metadata, dict):
            return

        enriched_metadata = {
            **existing_metadata,
            **self._review_service.build_persisted_action_metadata(
                step_id=step_id,
                function_call_index=function_call_index,
                function_call=function_call,
                reasoning=reasoning,
                ambiguity_candidate=ambiguity_candidate,
                artifacts=artifacts,
            ),
        }
        temp_file_path = metadata_file_path.with_name(f"{metadata_file_path.name}.tmp")

        try:
            temp_file_path.write_text(
                json.dumps(enriched_metadata, indent=2) + "\n",
                encoding="utf-8",
            )
            temp_file_path.replace(metadata_file_path)
        except OSError:
            temp_file_path.unlink(missing_ok=True)
