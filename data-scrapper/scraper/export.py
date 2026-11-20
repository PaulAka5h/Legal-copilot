"""Build sections.jsonl from existing Act JSON files, without re-scraping.

Each Act file in data/processed/acts/ already holds section records in the
sections.jsonl schema. This flattens them in a deterministic order (numeric
act_id, then the Act's own section order) and writes only records that pass
DataValidator. A record repeating a document_id and source_url is a duplicate
and is dropped. A record repeating a document_id with a different source_url
is a different section (scraper ID collision): it is kept, with the bdlaws
section number from its URL appended to the ID. Rejects, duplicates and
renamed IDs are listed in a report by ID only (no legal text).
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

from scraper.validator import DataValidator


def _act_sort_key(path: Path) -> Tuple[int, str]:
    stem = path.stem.removeprefix("act_")
    return (int(stem), "") if stem.isdigit() else (10**9, stem)


def _disambiguated_id(record: Dict[str, Any]) -> str:
    match = re.search(r"/section-(\d+)\.html", record.get("source_url", ""))
    suffix = match.group(1) if match else record.get("content_hash", "")[:8]
    return f"{record['document_id']}-s{suffix}"


def iter_act_sections(acts_dir: Path) -> Iterator[Dict[str, Any]]:
    """Yield section records from every Act file in deterministic order."""
    for act_file in sorted(acts_dir.glob("act_*.json"), key=_act_sort_key):
        with open(act_file, "r", encoding="utf-8") as f:
            act = json.load(f)
        yield from act.get("sections", [])


def export_sections(acts_dir: Path, out_path: Path, report_path: Path) -> Dict[str, Any]:
    """Write validated, de-duplicated sections to out_path atomically; return a summary."""
    seen: Dict[str, str] = {}  # document_id -> source_url
    rejected: List[Dict[str, Any]] = []
    duplicates: List[str] = []
    renamed: List[Dict[str, str]] = []
    written = 0
    languages: Dict[str, int] = {}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=out_path.parent, suffix=".jsonl.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            for record in iter_act_sections(acts_dir):
                doc_id = record.get("document_id")
                if doc_id in seen:
                    if seen[doc_id] == record.get("source_url"):
                        duplicates.append(doc_id)
                        continue
                    new_id = _disambiguated_id(record)
                    renamed.append({"original_id": doc_id, "new_id": new_id})
                    record = {**record, "document_id": new_id}
                    doc_id = new_id
                seen[doc_id] = record.get("source_url")

                issues = DataValidator.validate_section_record(record)
                if issues:
                    rejected.append({
                        "document_id": doc_id,
                        "act_id": record.get("act_id"),
                        "language": record.get("language"),
                        "issues": issues,
                    })
                    continue

                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
                lang = record.get("language", "unknown")
                languages[lang] = languages.get(lang, 0) + 1
        os.replace(tmp_name, out_path)
    except BaseException:
        os.unlink(tmp_name)
        raise

    summary = {
        "written": written,
        "by_language": languages,
        "rejected_count": len(rejected),
        "duplicate_count": len(duplicates),
        "renamed_id_count": len(renamed),
        "output": str(out_path),
    }
    report = {**summary, "rejected": rejected, "duplicates": duplicates, "renamed_ids": renamed}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return summary
