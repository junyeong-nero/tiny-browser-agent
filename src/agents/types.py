from dataclasses import dataclass, field
from typing import Literal

GroundingMode = Literal["vision", "text", "mixed"]


@dataclass
class Subgoal:
    id: int
    description: str
    success_criteria: str
    status: Literal["pending", "active", "done", "failed"] = field(default="pending")
