from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 开发环境默认数据库 URL（仅用于本地开发，不包含生产密码）
_DEV_DATABASE_URL = "postgresql+psycopg://truman:truman@localhost:5432/trumanworld"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRUMANWORLD_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    api_prefix: str = "/api"
    # 数据库 URL 必须通过环境变量 TRUMANWORLD_DATABASE_URL 提供
    # 开发环境可使用: postgresql+psycopg://truman:truman@localhost:5432/trumanworld
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    agent_backend: Literal["heuristic", "claude_sdk", "langgraph"] = "heuristic"
    agent_model: str | None = None
    agent_budget_usd: float = 1.0
    langgraph_model: str | None = None
    langgraph_api_key: str | None = None
    langgraph_base_url: str | None = None
    langgraph_reactor_structured_enabled: bool = False
    langgraph_reactor_prompt_cache_enabled: bool = True
    langgraph_reactor_max_concurrency: int = 4
    anthropic_model: str | None = None
    log_level: str = "INFO"
    project_root: Path = PROJECT_ROOT
    claude_sdk_isolated_home_enabled: bool = True
    claude_sdk_home_dir: Path | None = None
    claude_sdk_reactor_pool_enabled: bool = True

    # 导演智能体配置（实验性功能）
    director_auto_intervention_enabled: bool = False
    director_backend: Literal["heuristic", "claude_sdk", "langgraph"] = "claude_sdk"
    director_agent_model: str | None = None
    director_decision_interval: int = 1
    scheduler_interval_seconds: float = 1.0
    # 连续失败多少次后自动暂停（0 表示不限制）
    scheduler_max_consecutive_errors: int = 5

    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            # Docker 环境
            "http://127.0.0.1:33100",
            "http://localhost:33100",
            # 默认 Next.js 端口
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            # Makefile dev 端口
            "http://127.0.0.1:13000",
            "http://localhost:13000",
        ]
    )

    @model_validator(mode="after")
    def normalize_agent_settings(self) -> "Settings":
        # 数据库 URL 验证：开发环境提供默认值，生产环境必须显式配置
        if self.database_url is None:
            if self.app_env == "development":
                self.database_url = _DEV_DATABASE_URL
            else:
                raise ValueError(
                    "TRUMANWORLD_DATABASE_URL must be set in non-development environments"
                )

        if self.agent_model is None and self.anthropic_model is not None:
            self.agent_model = self.anthropic_model
        if self.langgraph_model is None and self.agent_model is not None:
            self.langgraph_model = self.agent_model
        if self.langgraph_api_key is None and self.anthropic_api_key is not None:
            self.langgraph_api_key = self.anthropic_api_key
        if self.langgraph_base_url is None and self.anthropic_base_url is not None:
            self.langgraph_base_url = self.anthropic_base_url
        if self.claude_sdk_home_dir is None:
            self.claude_sdk_home_dir = self.project_root / ".claude-sdk-home"
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
