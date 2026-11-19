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


def test_revision_ids_fit_alembic_version_column() -> None:
    """alembic_version.version_num is varchar(32); a longer ID fails only at apply time."""
    import re

    ids = [
        re.search(r'^revision = "([^"]+)"', path.read_text(encoding="utf-8"), re.M).group(1)
        for path in (BACKEND_DIR / "alembic" / "versions").glob("*.py")
    ]
    assert ids
    assert [i for i in ids if len(i) > 32] == []
