"""Summarizer package for action review and end-user summaries."""

from importlib import import_module

__all__ = [
    "ActionMetadataWriter",
    "ActionReviewContext",
    "ActionReviewService",
    "ActionStepSummarizer",
    "ActionStepSummarizerProtocol",
    "ActionStepSummary",
    "ActionSummaryTextProvider",
    "AmbiguityCandidate",
    "detect_ambiguity_candidate",
]


def __getattr__(name: str):
    if name in __all__:
        return getattr(import_module(".agent", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
