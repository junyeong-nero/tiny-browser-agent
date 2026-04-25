import config as app_config


def test_default_actor_uses_openrouter_model():
    assert app_config.actor_provider() == "openrouter"
    assert app_config.actor_model() == "nvidia/nemotron-3-super-120b-a12b:free"


def test_default_planner_uses_gemini_model():
    assert app_config.planner_provider() == "gemini"
    assert app_config.planner_model() == "gemini-3-flash-preview"
