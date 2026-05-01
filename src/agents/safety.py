from collections.abc import Callable
from typing import Any, Literal

import termcolor


SafetyDecision = Literal["CONTINUE", "TERMINATE"]
SafetyConfirmationCallback = Callable[[dict[str, Any]], SafetyDecision]


def prompt_for_safety_confirmation(safety: dict[str, Any]) -> SafetyDecision:
    """Ask for CLI confirmation for a model-requested safety decision."""
    if safety["decision"] != "require_confirmation":
        raise ValueError(f"Unknown safety decision: {safety['decision']}")

    termcolor.cprint(
        "Safety service requires explicit confirmation!",
        color="yellow",
        attrs=["bold"],
    )
    print(safety["explanation"])
    decision = ""
    while decision.lower() not in ("y", "n", "ye", "yes", "no"):
        decision = input("Do you wish to proceed? [Yes]/[No]\n")
    if decision.lower() in ("n", "no"):
        return "TERMINATE"
    return "CONTINUE"
