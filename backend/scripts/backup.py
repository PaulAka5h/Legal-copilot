"""Database backup script using pg_dump via Docker Compose.

Connects to the PostgreSQL container as the postgres superuser (trust auth on
local socket inside the container) and dumps the legal_copilot_test database.

Usage:
    python -m scripts.backup [--output backup_dir]
"""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def run_backup(output_dir: Path | None = None) -> Path:
    """Create a pg_dump backup of the legal_copilot_test database.

    Returns the path to the backup file.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parents[1] / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"legal_copilot_test_{timestamp}.sql"

    # pg_dump runs inside the db container, connecting to the local PostgreSQL
    # as the postgres superuser (trust auth for local socket connections).
    cmd = [
        "docker",
        "compose",
        "-f",
        str(Path(__file__).resolve().parents[2] / "compose.yaml"),
        "exec",
        "-T",
        "db",
        "pg_dump",
        "-U", "postgres",
        "-d", "legal_copilot_test",
        "--no-owner",
        "--clean",
        "--if-exists",
    ]

    with open(backup_file, "w", encoding="utf-8") as fh:
        result = subprocess.run(
            cmd,
            stdout=fh,
            stderr=subprocess.PIPE,
            text=True,
        )

    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    print(f"Backup written to {backup_file}")
    return backup_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup the PokkhoAI database.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Directory to write the backup file (default: backend/backups/)",
    )
    args = parser.parse_args()
    run_backup(args.output)


if __name__ == "__main__":
    main()
