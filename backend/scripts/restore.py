"""Database restore script using psql via Docker Compose.

Restores a pg_dump backup into the legal_copilot_test database.

Usage:
    python -m scripts.restore <backup_file>
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run_restore(backup_file: Path) -> None:
    """Restore a pg_dump backup into the legal_copilot_test database.

    The backup is piped into psql inside the db container as the postgres
    superuser.
    """
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    # psql runs inside the db container, reading the backup from stdin.
    # We open the backup file and pass it as stdin to the psql process.
    cmd = [
        "docker",
        "compose",
        "-f",
        str(Path(__file__).resolve().parents[2] / "compose.yaml"),
        "exec",
        "-T",
        "db",
        "psql",
        "-U", "postgres",
        "-d", "legal_copilot_test",
        "-v", "ON_ERROR_STOP=1",
    ]

    with open(backup_file, "r", encoding="utf-8") as fh:
        result = subprocess.run(
            cmd,
            stdin=fh,
            stderr=subprocess.PIPE,
            text=True,
        )

    if result.returncode != 0:
        raise RuntimeError(f"pg_restore/psql failed: {result.stderr}")

    print(f"Restore completed from {backup_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore the PokkhoAI database from backup.")
    parser.add_argument(
        "backup_file",
        type=Path,
        help="Path to the backup .sql file to restore",
    )
    args = parser.parse_args()
    run_restore(args.backup_file)


if __name__ == "__main__":
    main()
