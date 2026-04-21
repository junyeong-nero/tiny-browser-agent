import json
from typing import Optional

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
    ) -> None:
        self._query = query
        self._llm_client = llm_client or LLMClient.from_env()
        self._model_name = model_name or app_config.planner_model()

    def plan(self) -> list[Subgoal]:
        """Decompose the query into a list of subgoals."""
        prompt = f"{_PLANNER_SYSTEM_PROMPT}\n\nUser query:\n{self._query}"
        return self._call_planner(prompt, start_id=1)

    def replan(
        self,
        current_subgoal: Subgoal,
        failure_reason: str,
        remaining: list[Subgoal],
    ) -> list[Subgoal]:
        """Re-plan remaining subgoals after a failure."""
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
        return self._call_planner(prompt, start_id=start_id)

    def _call_planner(self, prompt: str, start_id: int) -> list[Subgoal]:
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            )
        ]
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[_SubgoalSchema],
            temperature=0.3,
        )
        response = self._llm_client.generate_content(
            model=self._model_name,
            contents=contents,
            config=config,
        )
        raw_text = response.candidates[0].content.parts[0].text or "[]"

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Attempt to extract JSON array from surrounding text
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1
            data = json.loads(raw_text[start:end]) if start != -1 else []

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
