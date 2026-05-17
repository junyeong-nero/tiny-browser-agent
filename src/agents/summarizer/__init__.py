"""Summarizer package for action review and end-user summaries."""

from importlib import import_module

_EXPORT_MODULES = {
    "ActionMetadataWriter": ".metadata_writer",
    "ActionReviewContext": ".ambiguity",
    "ActionReviewService": ".review_service",
    "ActionStepSummarizer": ".step_summarizer",
    "ActionStepSummarizerProtocol": ".types",
    "ActionStepSummary": ".types",
    "ActionSummaryTextProvider": ".types",
    "AmbiguityCandidate": ".ambiguity",
    "detect_ambiguity_candidate": ".ambiguity",
}

__all__ = sorted(_EXPORT_MODULES)


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is not None:
        return getattr(import_module(module_name, __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
