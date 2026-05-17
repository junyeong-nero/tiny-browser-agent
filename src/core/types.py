from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

GroundingMode = Literal["vision", "text", "mixed"]


@dataclass
class Subgoal:
    id: int
    description: str
    success_criteria: str
    status: Literal["pending", "active", "done", "failed"] = field(default="pending")


AgentRunStatus = Literal["complete", "failed", "blocked", "partial_failure", "interrupted"]


@dataclass(frozen=True)
class AgentRunResult:
    status: AgentRunStatus
    reason: str | None = None
    summary: str | None = None
    succeeded_subgoals: int = 0
    failed_subgoals: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "complete"

