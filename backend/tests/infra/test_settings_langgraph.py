from app.infra.settings import Settings


def test_settings_support_langgraph_specific_model_config() -> None:
    settings = Settings(
        agent_backend="langgraph",
        langgraph_model="claude-test",
        langgraph_api_key="langgraph-key",
        langgraph_base_url="https://example.invalid/anthropic",
    )

    assert settings.langgraph_model == "claude-test"
    assert settings.langgraph_api_key == "langgraph-key"
    assert settings.langgraph_base_url == "https://example.invalid/anthropic"


def test_settings_backfill_langgraph_config_from_existing_anthropic_fields() -> None:
    settings = Settings(
        agent_backend="langgraph",
        agent_model="agent-fallback-model",
        anthropic_api_key="anthropic-key",
        anthropic_base_url="https://anthropic-proxy.invalid",
    )

    assert settings.langgraph_model == "agent-fallback-model"
    assert settings.langgraph_api_key == "anthropic-key"
    assert settings.langgraph_base_url == "https://anthropic-proxy.invalid"
