"""Stream scraper sections.jsonl, validate each record, and group records by Act.

Validation uses the scraper's own DataValidator (data-scrapper/scraper/validator.py)
so ingestion and export apply the same rules. Invalid lines become rejects that
carry only IDs and issue names, never legal text.
"""

import importlib.util
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRAPER_VALIDATOR = REPO_ROOT / "data-scrapper" / "scraper" / "validator.py"


def load_validator() -> Any:
    """Load DataValidator from the scraper without adding the scraper to sys.path."""
    spec = importlib.util.spec_from_file_location("scraper_validator", SCRAPER_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Scraper validator not found at {SCRAPER_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DataValidator


@dataclass(frozen=True)
class ActBatch:
    """All validated sections of one Act in one language, in source order."""

    act_id: str
    language: str
    records: tuple[dict[str, Any], ...]


@dataclass
class Rejects:
    items: list[dict[str, Any]] = field(default_factory=list)

    def add(self, line_no: int, document_id: Any, issues: list[str]) -> None:
        self.items.append({"line": line_no, "document_id": document_id, "issues": issues})


def iter_act_batches(
    path: Path,
    rejects: Rejects,
    language: str | None = None,
    validator: Any = None,
    act_ids: set[str] | None = None,
) -> Iterator[ActBatch]:
    """Yield one ActBatch per consecutive run of (act_id, language) records.

    The input must be grouped by Act (as `main.py --export-sections` writes it).
    A key that reappears after another Act raises ValueError, because splitting
    one Act across batches would create spurious source versions.
    """
    validator = validator or load_validator()
    seen_keys: set[tuple[str, str]] = set()
    key: tuple[str, str] | None = None
    batch: list[dict[str, Any]] = []

    with open(path, "r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                rejects.add(line_no, None, ["Invalid JSON"])
                continue
            if language and record.get("language") != language:
                continue
            if act_ids and str(record.get("act_id")) not in act_ids:
                continue
            issues = validator.validate_section_record(record)
            if record.get("language") not in ("bn", "en"):
                issues = [*issues, "language must be bn or en"]
            if issues:
                rejects.add(line_no, record.get("document_id"), issues)
                continue

            record_key = (str(record["act_id"]), record["language"])
            if record_key != key:
                if batch and key is not None:
                    yield ActBatch(key[0], key[1], tuple(batch))
                if record_key in seen_keys:
                    raise ValueError(f"Input is not grouped by Act: {record_key} reappears at line {line_no}")
                seen_keys.add(record_key)
                key, batch = record_key, []
            batch.append(record)

    if batch and key is not None:
        yield ActBatch(key[0], key[1], tuple(batch))
