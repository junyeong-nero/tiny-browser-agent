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

When planning:
- Identify the browser actions and observations required to satisfy the user's goal.
- Prefer the fewest reliable subgoals that still let the browser agent verify progress.
- Make each subgoal concrete enough to determine completion from page state or tool results.
- Do not split tightly coupled interactions such as "click X then type Y" into unnecessary micro-steps.
- Include navigation, extraction, verification, and fallback steps when they are needed for the goal.
- If the goal is already a single browser action, return a single subgoal.
- If the user specifies a target website, web app, or service, preserve that scope in every subgoal.
- For site-specific tasks, use the target site's own search, filters, forms, and navigation; do not create fallback subgoals that switch to external search engines.
- If the scoped site cannot complete the task, make the final fallback a blocker report rather than an out-of-scope search.
- Do not name a search provider such as Google, Naver, Bing, or DuckDuckGo unless
  the user explicitly requested that provider or the current task is about that provider.
- For generic web searches, say to use the browser's default search engine or search
  tool; leave provider choice to the browser agent and runtime configuration.

Output format (STRICT):
- Respond ONLY with JSON. No prose, no markdown fences, no commentary.
- The JSON must be an array of objects: [{...}, {...}, ...].
- Each object MUST have exactly these two fields, both non-empty strings:
    "description": what the browser agent should do at this step.
    "success_criteria": how to verify this step succeeded from the page state.
- Do NOT add other fields (no "action", "target", "query", "id", etc.).
- If a JSON object wrapper is required by your runtime, wrap as
  {"subgoals": [...]} using the same item schema.
"""

_REPLAN_SYSTEM_PROMPT = """You are a planning agent for a web browser automation system.
A subgoal has failed or become blocked. Re-plan the remaining work given the failure context.

When re-planning:
- Preserve the original user goal.
- Avoid repeating the failed path unless the failure context suggests a simple retry is appropriate.
- Return only concrete replacement subgoals that a browser agent can execute and verify.
- Prefer a short fallback plan over a long speculative plan.
- Preserve any target website, web app, or service scope from the original user goal.
- For site-specific tasks, retry in-scope navigation/search/filtering first; if blocked, report the blocker instead of switching to external search engines.
- Do not switch to or name a specific search provider such as Google, Naver, Bing,
  or DuckDuckGo unless the user explicitly requested that provider or the failure
  context proves that provider is necessary.
- For generic web-search fallbacks, say to use the browser's default search engine
  or search tool instead of naming providers.

Output format (STRICT):
- Respond ONLY with JSON. No prose, no markdown fences, no commentary.
- The JSON must be an array of objects: [{...}, {...}, ...].
- Each object MUST have exactly these two fields, both non-empty strings:
    "description": what the browser agent should do at this step.
    "success_criteria": how to verify this step succeeded from the page state.
- Do NOT add other fields (no "action", "target", "query", "id", etc.).
- If a JSON object wrapper is required by your runtime, wrap as
  {"subgoals": [...]} using the same item schema.
"""


_SUBGOAL_KEYS = ("description", "success_criteria", "task", "step", "goal")


def _first_string(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _try_extract_json(text: str) -> Any:
    """Best-effort extraction of an embedded JSON object or array."""
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start == -1 or end <= start:
            continue
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            continue
    return None


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped
    body = lines[1:]
    if body and body[-1].strip().startswith("```"):
        body = body[:-1]
    return "\n".join(body).strip()


def _looks_like_subgoal(item: Any) -> bool:
    return isinstance(item, dict) and any(k in item for k in _SUBGOAL_KEYS)


def _coerce_to_subgoal_list(value: Any) -> list[dict[str, Any]] | None:
    """Find a list of subgoal dicts inside the model's JSON output.

    Tolerates: bare list, single subgoal dict, `{"subgoals": [...]}`,
    arbitrarily-named wrapper keys, nested wrappers (e.g. `{"plan": {"steps": [...]}}`).
    """
    if isinstance(value, list):
        if any(_looks_like_subgoal(item) for item in value):
            return value
        return value if not value else None
    if isinstance(value, dict):
        if _looks_like_subgoal(value):
            return [value]
        for child in value.values():
            found = _coerce_to_subgoal_list(child)
            if found is not None:
                return found
    return None


def _extract_answer_text(response: Any) -> str:
    """Return all non-thought text parts from a model response.

    OpenAI/OpenRouter-style providers may surface reasoning as a leading
    `thought=True` part; reading `parts[0]` blindly would give the chain of
    thought instead of the JSON answer. Some providers also split JSON answers
    across multiple text parts, so preserve every non-thought text part in
    response order.
    """
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) or []
    text_parts = []
    for part in parts:
        if getattr(part, "thought", None) is True:
            continue
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            text_parts.append(text)
    return "".join(text_parts).strip()


class _SubgoalSchema(BaseModel):
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
        planner_config = app_config.planner_config()
        self._llm_client = llm_client or LLMClient.from_provider_name(planner_config.provider)
        self._model_name = model_name or planner_config.model
        self._event_sink = event_sink

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if not self._event_sink:
            return
        self._event_sink({"type": event_type, "timestamp": time.time(), **payload})

    def plan(self) -> list[Subgoal]:
        """Decompose the query into a list of subgoals."""
        self._emit_event("planner_started", query=self._query)
        prompt = f"User query:\n{self._query}"
        subgoals = self._call_planner(
            prompt,
            start_id=1,
            system_prompt=_PLANNER_SYSTEM_PROMPT,
        )
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
        *,
        outcomes: list[tuple[Subgoal, str, str]] | None = None,
        latest_url: str | None = None,
    ) -> list[Subgoal]:
        """Re-plan remaining subgoals after a failure."""
        self._emit_event(
            "planner_replanning",
            failed_subgoal_id=current_subgoal.id,
            failure_reason=failure_reason,
        )
        remaining_text = "\n".join(
            f"- [{sg.id}] {sg.description} (success criteria: {sg.success_criteria})"
            for sg in remaining
        ) or "None."
        outcome_lines = []
        for subgoal, status, reason in outcomes or []:
            compact_reason = " ".join(str(reason).split())[:500]
            outcome_lines.append(
                f"- [{subgoal.id}] {status}: {subgoal.description} — {compact_reason}"
            )
        outcomes_text = "\n".join(outcome_lines) or "None yet."
        prompt = (
            f"Original query:\n{self._query}\n\n"
            f"Latest browser URL: {latest_url or 'unknown'}\n\n"
            "Prior successful/failed subgoal outcomes:\n"
            f"{outcomes_text}\n\n"
            f"Failed subgoal [{current_subgoal.id}]: {current_subgoal.description}\n"
            f"Failure reason: {failure_reason}\n\n"
            f"Current remaining planned subgoals:\n{remaining_text}\n\n"
            "Provide a revised list of subgoals to complete the original query. "
            "If no in-scope path remains, return one final subgoal that reports the blocker."
        )
        start_id = current_subgoal.id + 1
        subgoals = self._call_planner(
            prompt,
            start_id=start_id,
            system_prompt=_REPLAN_SYSTEM_PROMPT,
        )
        self._emit_event(
            "planner_replanned",
            failed_subgoal_id=current_subgoal.id,
            subgoals=[{"id": sg.id, "description": sg.description, "success_criteria": sg.success_criteria} for sg in subgoals],
        )
        return subgoals

    def _parse_subgoal_json(self, raw_text: str) -> list[dict[str, Any]]:
        """Parse the planner response into a list of dicts, emitting an error
        event if the payload is not valid JSON.
        """
        raw_text = _strip_code_fences(raw_text)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = _try_extract_json(raw_text)
            if parsed is None:
                self._emit_event(
                    "planner_parse_error",
                    error_message="response is not valid JSON",
                    raw_text=raw_text[:500],
                )
                return []
        unwrapped = _coerce_to_subgoal_list(parsed)
        if unwrapped is None:
            self._emit_event(
                "planner_parse_error",
                error_message=f"could not find a subgoal list in {type(parsed).__name__}",
                raw_text=raw_text[:500],
            )
            return []
        return unwrapped

    def _call_planner(
        self,
        prompt: str,
        start_id: int,
        system_prompt: str,
    ) -> list[Subgoal]:
        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            )
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=genai_types.Content(
                role="system",
                parts=[genai_types.Part(text=system_prompt)],
            ),
            temperature=0.3,
            response_mime_type="application/json",
            response_schema=list[_SubgoalSchema],
        )
        response = self._llm_client.generate_content(
            model=self._model_name,
            contents=contents,
            config=config,
        )
        raw_text = _extract_answer_text(response) or "[]"
        self._emit_event("planner_raw_response", raw_text=raw_text[:2000])
        data = self._parse_subgoal_json(raw_text)

        subgoals = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                self._emit_event(
                    "planner_parse_error",
                    error_message=f"expected dict, got {type(item).__name__}",
                    raw_text=str(item)[:500],
                )
                continue
            description = _first_string(item, ("description", "task", "step", "goal"))
            success_criteria = _first_string(
                item, ("success_criteria", "criteria", "done_when", "verification")
            )
            if not description:
                self._emit_event(
                    "planner_parse_error",
                    error_message="subgoal missing description",
                    raw_text=str(item)[:500],
                )
                continue
            if not success_criteria:
                success_criteria = f"Step is complete when: {description}"
            subgoals.append(
                Subgoal(
                    id=start_id + idx,
                    description=description,
                    success_criteria=success_criteria,
                )
            )
        return subgoals
