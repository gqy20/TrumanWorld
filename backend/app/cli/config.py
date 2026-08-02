from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:18080/api"


class CliConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CliConfig:
    base_url: str = DEFAULT_BASE_URL
    admin_password: str | None = None
    timeout: float = 120.0
    output: str = "table"
    profile: str = "default"
    config_path: Path | None = None


def default_config_path() -> Path:
    root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "trumanworld" / "config.toml"


def _profile_data(path: Path, profile: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CliConfigError(f"Cannot read config {path}: {exc}") from exc
    profiles = raw.get("profiles", {})
    if not isinstance(profiles, dict):
        raise CliConfigError("Config field 'profiles' must be a table")
    data = profiles.get(profile, {})
    if not isinstance(data, dict):
        raise CliConfigError(f"Profile '{profile}' must be a table")
    return data


def load_config(
    *,
    profile: str = "default",
    base_url: str | None = None,
    timeout: float | None = None,
    output: str | None = None,
    environ: dict[str, str] | None = None,
) -> CliConfig:
    env = environ if environ is not None else os.environ
    path = Path(env.get("TRUMANWORLD_CLI_CONFIG", default_config_path())).expanduser()
    data = _profile_data(path, profile)
    resolved_url = (
        base_url or env.get("TRUMANWORLD_CLI_BASE_URL") or data.get("base_url") or DEFAULT_BASE_URL
    )
    resolved_timeout = timeout or float(
        env.get("TRUMANWORLD_CLI_TIMEOUT") or data.get("timeout") or 120
    )
    resolved_output = output or env.get("TRUMANWORLD_CLI_OUTPUT") or data.get("output") or "table"
    if resolved_output not in {"table", "json", "ndjson"}:
        raise CliConfigError("Output must be table, json, or ndjson")
    if resolved_timeout <= 0:
        raise CliConfigError("Timeout must be positive")
    return CliConfig(
        base_url=str(resolved_url).rstrip("/"),
        admin_password=env.get("TRUMANWORLD_DEMO_ADMIN_PASSWORD"),
        timeout=float(resolved_timeout),
        output=str(resolved_output),
        profile=profile,
        config_path=path,
    )
