from app.infra.settings import Settings


def test_settings_support_langgraph_specific_model_config() -> None:
    settings = Settings(
        agent_backend="langgraph",
        llm_model="claude-test",
        llm_api_key="langgraph-key",
        llm_base_url="https://example.invalid/anthropic",
    )

    assert settings.llm_model == "claude-test"
    assert settings.llm_api_key == "langgraph-key"
    assert settings.llm_base_url == "https://example.invalid/anthropic"


def test_settings_backfill_langgraph_config_from_existing_anthropic_fields() -> None:
    settings = Settings(
        agent_backend="langgraph",
        llm_provider="anthropic",
        llm_model="agent-fallback-model",
        llm_api_key="",
        llm_base_url="",
        anthropic_api_key="anthropic-key",
        anthropic_base_url="https://anthropic-proxy.invalid",
    )

    assert settings.llm_model == "agent-fallback-model"
    assert settings.llm_api_key == "anthropic-key"
    assert settings.llm_base_url == "https://anthropic-proxy.invalid"


def test_settings_default_llm_provider_is_anthropic() -> None:
    settings = Settings(agent_backend="langgraph", llm_provider="anthropic")

    assert settings.llm_provider == "anthropic"


def test_settings_support_openai_llm_provider() -> None:
    settings = Settings(
        agent_backend="langgraph",
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        llm_api_key="openai-key",
        llm_base_url="https://example.invalid/v1",
        llm_enable_thinking=False,
        llm_thinking_budget=128,
        llm_session_cache_enabled=True,
    )

    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.llm_api_key == "openai-key"
    assert settings.llm_base_url == "https://example.invalid/v1"
    assert settings.llm_enable_thinking is False
    assert settings.llm_thinking_budget == 128
    assert settings.llm_session_cache_enabled is True


def test_settings_backfill_claude_sdk_fields_from_anthropic_llm_settings() -> None:
    settings = Settings(
        agent_backend="claude_sdk",
        llm_provider="anthropic",
        llm_model="claude-sonnet-test",
        llm_api_key="anthropic-key",
        llm_base_url="https://anthropic-proxy.invalid",
    )

    assert settings.llm_model == "claude-sonnet-test"
    assert settings.anthropic_api_key == "anthropic-key"
    assert settings.anthropic_base_url == "https://anthropic-proxy.invalid"


def test_settings_do_not_backfill_claude_sdk_fields_from_openai_llm_settings() -> None:
    settings = Settings(
        agent_backend="claude_sdk",
        llm_provider="openai",
        llm_model="gpt-4.1-mini",
        llm_api_key="openai-key",
        llm_base_url="https://example.invalid/v1",
    )

    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.anthropic_api_key is None
    assert settings.anthropic_base_url is None
