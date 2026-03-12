from __future__ import annotations

from claude_agent_sdk import ClaudeAgentOptions

from app.infra.settings import Settings


def build_sdk_env(settings: Settings) -> dict[str, str]:
    env: dict[str, str] = {}
    anthropic_api_key = getattr(settings, "anthropic_api_key", None)
    anthropic_base_url = getattr(settings, "anthropic_base_url", None)
    isolated_home_enabled = bool(getattr(settings, "claude_sdk_isolated_home_enabled", False))
    isolated_home_dir = getattr(settings, "claude_sdk_home_dir", None)

    if anthropic_api_key:
        env["ANTHROPIC_API_KEY"] = anthropic_api_key
    if anthropic_base_url:
        env["ANTHROPIC_BASE_URL"] = anthropic_base_url

    if isolated_home_enabled and isolated_home_dir is not None:
        home_dir = isolated_home_dir
        xdg_dir = home_dir / "xdg"
        cache_dir = home_dir / "cache"
        state_dir = home_dir / "state"
        for path in (home_dir, xdg_dir, cache_dir, state_dir):
            path.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home_dir)
        env["XDG_CONFIG_HOME"] = str(xdg_dir)
        env["XDG_CACHE_HOME"] = str(cache_dir)
        env["XDG_STATE_HOME"] = str(state_dir)

    return env


def apply_sdk_isolation(options: ClaudeAgentOptions, settings: Settings) -> ClaudeAgentOptions:
    if not bool(getattr(settings, "claude_sdk_isolated_home_enabled", False)):
        return options
    return ClaudeAgentOptions(
        tools=options.tools,
        allowed_tools=list(options.allowed_tools),
        system_prompt=options.system_prompt,
        mcp_servers=options.mcp_servers,
        permission_mode=options.permission_mode,
        continue_conversation=options.continue_conversation,
        resume=options.resume,
        max_turns=options.max_turns,
        max_budget_usd=options.max_budget_usd,
        disallowed_tools=list(options.disallowed_tools),
        model=options.model,
        fallback_model=options.fallback_model,
        betas=list(options.betas),
        permission_prompt_tool_name=options.permission_prompt_tool_name,
        cwd=options.cwd,
        cli_path=options.cli_path,
        settings=options.settings if options.settings is not None else "{}",
        add_dirs=list(options.add_dirs),
        env=dict(options.env),
        extra_args=dict(options.extra_args),
        max_buffer_size=options.max_buffer_size,
        debug_stderr=options.debug_stderr,
        stderr=options.stderr,
        can_use_tool=options.can_use_tool,
        hooks=options.hooks,
        user=options.user,
        include_partial_messages=options.include_partial_messages,
        fork_session=options.fork_session,
        agents=options.agents,
        setting_sources=[],
        sandbox=options.sandbox,
        plugins=[],
        max_thinking_tokens=options.max_thinking_tokens,
        output_format=options.output_format,
        enable_file_checkpointing=options.enable_file_checkpointing,
    )


def build_sdk_options(settings: Settings, **kwargs) -> ClaudeAgentOptions:
    merged_env = build_sdk_env(settings)
    merged_env.update(kwargs.pop("env", {}))
    options = ClaudeAgentOptions(env=merged_env, **kwargs)
    return apply_sdk_isolation(options, settings)
