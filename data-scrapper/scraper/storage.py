"""Atomic file writing and storage management for JSON, JSONL, and HTML caches."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages reading and writing scraped data safely with atomic writes."""

    def __init__(self, base_data_dir: Path = config.DATA_DIR):
        self.base_data_dir = base_data_dir
        self.raw_dir = base_data_dir / "raw"
        self.processed_dir = base_data_dir / "processed"
        self.failed_dir = base_data_dir / "failed"
        self.reports_dir = base_data_dir / "reports"
        self.acts_dir = self.processed_dir / "acts"

        for p in [self.raw_dir, self.processed_dir, self.failed_dir, self.reports_dir, self.acts_dir]:
            p.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def atomic_write_text(filepath: Path, content: str, encoding: str = "utf-8") -> None:
        """Writes text content atomically using a temporary file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        # Create temp file in same directory to ensure atomic rename across filesystems
        temp_dir = filepath.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding=encoding) as tf:
            tf.write(content)
            temp_name = tf.name
        os.replace(temp_name, filepath)

    def save_json(self, filepath: Path, data: Any) -> None:
        """Saves data structure as pretty-printed JSON atomically."""
        content = json.dumps(data, ensure_ascii=False, indent=2)
        self.atomic_write_text(filepath, content)

    def load_json(self, filepath: Path, default: Any = None) -> Any:
        """Loads JSON data from file if exists, otherwise returns default."""
        if not filepath.exists():
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error reading JSON from %s: %s", filepath, e)
            return default

    def append_jsonl(self, filepath: Path, record: Dict[str, Any]) -> None:
        """Appends a single JSON record to a JSONL file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)

    def save_raw_html(self, act_id: str, section_id: Optional[str], content: str) -> Path:
        """Optionally caches raw downloaded HTML for debugging and provenance."""
        if section_id:
            filename = f"act_{act_id}_sec_{section_id}.html"
        else:
            filename = f"act_{act_id}.html"
        
        path = self.raw_dir / filename
        self.atomic_write_text(path, content)
        return path

    def save_act_data(self, act_id: str, data: Dict[str, Any]) -> Path:
        """Saves Act-level structured JSON file."""
        path = self.acts_dir / f"act_{act_id}.json"
        self.save_json(path, data)
        return path
