from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRUMANWORLD_", env_file=".env", extra="ignore")

    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/trumanworld"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str | None = None
    agent_provider: str = "heuristic"
    agent_model: str | None = None
    log_level: str = "INFO"
    project_root: Path = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
