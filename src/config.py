from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator
import yaml

LLMProviderName = Literal["gemini", "openai", "openrouter"]
SummaryProviderName = Literal["openai", "openrouter"]

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class LLMAgentModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LLMProviderName
    model: str

    @field_validator("model")
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


class SummaryAgentModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: SummaryProviderName
    model: str

    @field_validator("model")
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


class ModelsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor: LLMAgentModelConfig
    planner: LLMAgentModelConfig
    summary: SummaryAgentModelConfig


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    models: ModelsConfig


def _load() -> AppConfig:
    with open(_CONFIG_PATH) as f:
        loaded = yaml.safe_load(f) or {}
    return AppConfig.model_validate(loaded)


_config: AppConfig | None = None


def _get() -> AppConfig:
    global _config
    if _config is None:
        _config = _load()
    return _config


def actor_config() -> LLMAgentModelConfig:
    return _get().models.actor


def planner_config() -> LLMAgentModelConfig:
    return _get().models.planner


def summary_config() -> SummaryAgentModelConfig:
    return _get().models.summary


def actor_model() -> str:
    return actor_config().model


def actor_provider() -> LLMProviderName:
    return actor_config().provider


def planner_model() -> str:
    return planner_config().model


def planner_provider() -> LLMProviderName:
    return planner_config().provider


def summary_model() -> str:
    return summary_config().model


def summary_provider() -> SummaryProviderName:
    return summary_config().provider
