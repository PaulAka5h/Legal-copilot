"""Backup and restore drill test.

Verifies that the database can be backed up and restored.
Covers Security.md section 15: "Restore drill - Full restore from backup".
"""

import subprocess
from pathlib import Path

import pytest


def _run_backup() -> Path:
    """Run the backup script and return the backup file path."""
    result = subprocess.run(
        ["python", "-m", "scripts.backup"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Backup failed: {result.stderr}")
    for line in result.stdout.splitlines():
        if line.startswith("Backup written to "):
            return Path(line.split("Backup written to ", 1)[1].strip())
    raise RuntimeError("Could not parse backup file path from output")


def _run_restore(backup_file: Path) -> None:
    """Run the restore script."""
    result = subprocess.run(
        ["python", "-m", "scripts.restore", str(backup_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Restore failed: {result.stderr}")


def test_backup_creates_valid_file() -> None:
    """Backup creates a non-empty file containing expected SQL."""
    backup_file = _run_backup()
    try:
        assert backup_file.exists(), f"Backup file should exist: {backup_file}"
        assert backup_file.stat().st_size > 0, "Backup file should not be empty"

        # Verify backup contains expected content.
        content = backup_file.read_text(encoding="utf-8")
        assert "row_security = off" in content, "Backup should disable RLS for restore"
        assert "DROP POLICY IF EXISTS" in content, "Backup should drop RLS policies"
        assert "CREATE TABLE" in content, "Backup should contain table definitions"
        assert "COPY public." in content, "Backup should contain data COPY statements"
    finally:
        try:
            backup_file.unlink()
        except (FileNotFoundError, UnboundLocalError):
            pass


def test_restore_executes_without_error() -> None:
    """Restore script executes without error (creates clean schema)."""
    backup_file = _run_backup()
    try:
        assert backup_file.exists()

        # Restore should execute without error.
        _run_restore(backup_file)

        # If we reach here, restore succeeded.
    finally:
        try:
            backup_file.unlink()
        except (FileNotFoundError, UnboundLocalError):
            pass