from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

LLMProviderName = Literal["gemini", "openai", "openrouter", "nvidia"]
SummaryProviderName = Literal["openai", "openrouter", "nvidia"]

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


class ExecutionConstraintsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_steps_per_subgoal: int = 15
    max_total_steps: int = 100
    max_subgoals: int = 10

    @field_validator("max_steps_per_subgoal", "max_total_steps", "max_subgoals")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be greater than or equal to 1")
        return value


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    models: ModelsConfig
    constraints: ExecutionConstraintsConfig = Field(default_factory=ExecutionConstraintsConfig)


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


def execution_constraints() -> ExecutionConstraintsConfig:
    return _get().constraints


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


def max_steps_per_subgoal() -> int:
    return execution_constraints().max_steps_per_subgoal


def max_total_steps() -> int:
    return execution_constraints().max_total_steps


def max_subgoals() -> int:
    return execution_constraints().max_subgoals
