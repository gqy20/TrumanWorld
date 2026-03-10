from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRUMANWORLD_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/trumanworld"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    agent_provider: str = "heuristic"
    agent_model: str | None = None
    agent_budget_usd: float = 1.0
    anthropic_model: str | None = None
    log_level: str = "INFO"
    project_root: Path = PROJECT_ROOT

    # 导演智能体配置（实验性功能）
    director_agent_enabled: bool = True
    director_agent_model: str | None = None
    director_decision_interval: int = 1
    scheduler_interval_seconds: float = 5.0

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
        if self.agent_provider == "anthropic":
            self.agent_provider = "claude"
        if self.agent_model is None and self.anthropic_model is not None:
            self.agent_model = self.anthropic_model
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
