import config as app_config


def test_default_actor_uses_gemini_computer_use_model():
    assert app_config.actor_provider() == "gemini"
    assert app_config.actor_model() == "gemini-2.5-computer-use-preview-10-2025"
