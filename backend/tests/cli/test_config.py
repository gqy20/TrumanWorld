from pathlib import Path

import pytest

from app.cli.config import CliConfigError, load_config


def test_load_config_uses_profile_then_environment_then_arguments(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[profiles.default]\nbase_url = "https://profile.example/api"\ntimeout = 30\n',
        encoding="utf-8",
    )
    env = {
        "TRUMANWORLD_CLI_CONFIG": str(path),
        "TRUMANWORLD_CLI_BASE_URL": "https://env.example/api/",
        "TRUMANWORLD_DEMO_ADMIN_PASSWORD": "secret",
    }

    config = load_config(base_url="https://argument.example/api/", output="json", environ=env)

    assert config.base_url == "https://argument.example/api"
    assert config.timeout == 30
    assert config.output == "json"
    assert config.admin_password == "secret"


def test_load_config_rejects_invalid_output(tmp_path: Path):
    with pytest.raises(CliConfigError, match="Output must"):
        load_config(output="yaml", environ={"TRUMANWORLD_CLI_CONFIG": str(tmp_path / "none")})
