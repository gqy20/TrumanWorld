from pathlib import Path
from subprocess import run


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _dry_run(target: str) -> str:
    result = run(
        ["make", "--dry-run", target],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_default_dev_uses_dotenv_database_without_starting_local_postgres():
    output = _dry_run("dev")

    assert "uv run alembic upgrade head" in output
    assert "docker start trumanworld-db-test" not in output
    assert "TRUMANWORLD_DATABASE_URL=postgresql" not in output


def test_local_dev_is_the_explicit_container_database_workflow():
    output = _dry_run("local-dev")

    assert "docker start trumanworld-db-test" in output
    assert "TRUMANWORLD_DATABASE_URL=" in output
