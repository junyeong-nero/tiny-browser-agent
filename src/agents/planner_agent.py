import json
import time
from typing import Any, Callable, Optional

from google.genai import types as genai_types
from pydantic import BaseModel

import config as app_config

from agents.types import Subgoal
from llm import LLMClient


_PLANNER_SYSTEM_PROMPT = """You are a planning agent for a web browser automation system.
Your job is to decompose a user query into a sequence of concrete, actionable subgoals
that a browser agent can execute one at a time.

Each subgoal should:
- Describe a single, focused browser action or observation task
- Be specific enough for the agent to determine when it is complete
- Not be overly granular (avoid splitting "click X then type Y" into two subgoals)

Respond ONLY with a JSON array of subgoals. No other text.
"""

_REPLAN_SYSTEM_PROMPT = """You are a planning agent for a web browser automation system.
A subgoal has failed or become blocked. Re-plan the remaining work given the failure context.

Respond ONLY with a JSON array of replacement subgoals. No other text.
"""


class _SubgoalSchema(BaseModel):
    id: int
    description: str
    success_criteria: str


class PlannerAgent:
    def __init__(
        self,
        query: str,
        llm_client: Optional[LLMClient] = None,
        model_name: str | None = None,
        event_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self._query = query
        self._llm_client = llm_client or LLMClient.for_text()
        self._model_name = model_name or app_config.planner_model()
        self._event_sink = event_sink

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if not self._event_sink:
            return
        self._event_sink({"type": event_type, "timestamp": time.time(), **payload})

    def plan(self) -> list[Subgoal]:
        """Decompose the query into a list of subgoals."""
        self._emit_event("planner_started", query=self._query)
        prompt = f"{_PLANNER_SYSTEM_PROMPT}\n\nUser query:\n{self._query}"
        subgoals = self._call_planner(prompt, start_id=1)
        self._emit_event(
            "planner_completed",
            subgoals=[{"id": sg.id, "description": sg.description, "success_criteria": sg.success_criteria} for sg in subgoals],
        )
        return subgoals

    def replan(
        self,
        current_subgoal: Subgoal,
        failure_reason: str,
        remaining: list[Subgoal],
    ) -> list[Subgoal]:
        """Re-plan remaining subgoals after a failure."""
        self._emit_event(
            "planner_replanning",
            failed_subgoal_id=current_subgoal.id,
            failure_reason=failure_reason,
        )
        remaining_text = "\n".join(
            f"- [{sg.id}] {sg.description}" for sg in remaining
        )
        prompt = (
            f"{_REPLAN_SYSTEM_PROMPT}\n\n"
            f"Original query:\n{self._query}\n\n"
            f"Failed subgoal [{current_subgoal.id}]: {current_subgoal.description}\n"
            f"Failure reason: {failure_reason}\n\n"
            f"Remaining planned subgoals:\n{remaining_text}\n\n"
            "Provide a revised list of subgoals to complete the original query."
        )
        start_id = current_subgoal.id + 1
        subgoals = self._call_planner(prompt, start_id=start_id)
        self._emit_event(
            "planner_replanned",
            subgoals=[{"id": sg.id, "description": sg.description, "success_criteria": sg.success_criteria} for sg in subgoals],
        )
        return subgoals

    def _parse_subgoal_json(self, raw_text: str) -> list[dict[str, Any]]:
        """Parse the planner response into a list of dicts, emitting an error
        event if the payload is not valid JSON.
        """
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1
            if start == -1 or end <= start:
                self._emit_event(
                    "planner_parse_error",
                    error_message="response does not contain a JSON array",
                    raw_text=raw_text[:500],
                )
                return []
            try:
                parsed = json.loads(raw_text[start:end])
            except json.JSONDecodeError as exc:
                self._emit_event(
                    "planner_parse_error",
                    error_message=str(exc),
                    raw_text=raw_text[:500],
                )
                return []
        if not isinstance(parsed, list):
            self._emit_event(
                "planner_parse_error",
                error_message=f"expected JSON array, got {type(parsed).__name__}",
                raw_text=raw_text[:500],
            )
            return []
        return parsed

    def _call_planner(self, prompt: str, start_id: int) -> list[Subgoal]:
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            )
        ]
        config = genai_types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
            response_schema=list[_SubgoalSchema],
        )
        response = self._llm_client.generate_content(
            model=self._model_name,
            contents=contents,
            config=config,
        )
        raw_text = response.candidates[0].content.parts[0].text or "[]"
        data = self._parse_subgoal_json(raw_text)

        subgoals = []
        for idx, item in enumerate(data):
            subgoals.append(
                Subgoal(
                    id=start_id + idx,
                    description=item.get("description", ""),
                    success_criteria=item.get("success_criteria", ""),
                )
            )
        return subgoals
