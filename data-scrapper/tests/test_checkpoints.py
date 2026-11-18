"""Unit tests for Resumption and Checkpointing behavior (Phase 5)."""

import json
from pathlib import Path
from scraper.scraper import BDLawsScraper
from scraper.storage import StorageManager


def test_checkpoint_saving_and_loading(tmp_path: Path):
    storage = StorageManager(base_data_dir=tmp_path)
    scraper = BDLawsScraper(client=None, storage=storage)

    checkpoints = {
        "completed_acts": {"1": {"act_name": "Act 1", "sections_count": 1}},
        "partially_completed_acts": {"11": {"act_name": "Penal Code", "sections_count": 500, "failed_sections": []}},
        "failed_acts": {},
    }
    ckpt_file = tmp_path / "processed" / "checkpoints.json"
    storage.save_json(ckpt_file, checkpoints)

    loaded = storage.load_json(ckpt_file)
    assert loaded["completed_acts"]["1"]["act_name"] == "Act 1"
    assert "11" in loaded["partially_completed_acts"]
