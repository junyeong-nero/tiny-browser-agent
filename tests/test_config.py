import pytest

from config import AppConfig


def _minimal_config(**constraints):
    data = {
        "models": {
            "actor": {"provider": "openai", "model": "actor-model"},
            "planner": {"provider": "openai", "model": "planner-model"},
            "summary": {"provider": "openai", "model": "summary-model"},
        }
    }
    if constraints:
        data["constraints"] = constraints
    return data


def test_execution_constraints_have_agent_defaults_when_omitted():
    config = AppConfig.model_validate(_minimal_config())

    assert config.constraints.max_steps_per_subgoal == 15
    assert config.constraints.max_total_steps == 100
    assert config.constraints.max_subgoals == 10


def test_execution_constraints_can_be_configured():
    config = AppConfig.model_validate(
        _minimal_config(
            max_steps_per_subgoal=4,
            max_total_steps=12,
            max_subgoals=3,
        )
    )

    assert config.constraints.max_steps_per_subgoal == 4
    assert config.constraints.max_total_steps == 12
    assert config.constraints.max_subgoals == 3


def test_execution_constraints_reject_non_positive_values():
    with pytest.raises(ValueError):
        AppConfig.model_validate(_minimal_config(max_steps_per_subgoal=0))
