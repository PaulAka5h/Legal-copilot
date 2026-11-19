import re
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migrations_generate_offline_sql_with_required_schema_and_auth_support() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_DIR,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE EXTENSION IF NOT EXISTS vector" in result.stdout
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in result.stdout
    assert "CREATE EXTENSION IF NOT EXISTS citext" in result.stdout
    assert "CREATE POLICY lawyer_cases" in result.stdout
    assert "FORCE ROW LEVEL SECURITY" in result.stdout
    assert "CREATE FUNCTION app.lookup_login_user" in result.stdout
    assert "CREATE FUNCTION app.consume_login_attempt" in result.stdout
    assert "CREATE FUNCTION app.revoke_sessions" in result.stdout
    assert "CREATE TABLE public.audit_logs" in result.stdout


def _offline_upgrade_sql() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_DIR,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_every_app_function_used_by_a_policy_is_created_by_a_revision() -> None:
    sql = _offline_upgrade_sql()
    created = set(re.findall(r"CREATE (?:OR REPLACE )?FUNCTION app\.(\w+)", sql))
    used: set[str] = set()
    for policy in re.findall(r"CREATE POLICY.*?;", sql, flags=re.DOTALL):
        used.update(re.findall(r"app\.(\w+)\(", policy))

    assert used - created == set()


def test_strategy_tables_are_lawyer_only() -> None:
    sql = _offline_upgrade_sql()

    for policy in (
        "strategies_lawyer_manage",
        "strategy_scenarios_lawyer_manage",
        "strategy_comparisons_lawyer_manage",
    ):
        assert f"CREATE POLICY {policy}" in sql
    assert "strategies_client_read" not in sql
