"""Tests for HTTP client and Storage manager (Phase 2)."""

import json
from pathlib import Path
import pytest
import requests

from scraper.client import BDLawsClient
from scraper.storage import StorageManager


def test_decode_response_content():
    """Verify robust decoding of UTF-16 content."""
    mock_resp = requests.Response()
    raw_html = "<!DOCTYPE html><html><head><title>The Penal Code, 1860</title></head><body>Act</body></html>"
    mock_resp._content = raw_html.encode("utf-16")
    mock_resp.encoding = "utf-16"

    decoded = BDLawsClient.decode_response_content(mock_resp)
    assert "The Penal Code, 1860" in decoded
    assert "<!DOCTYPE html>" in decoded


def test_storage_manager_atomic_and_json(tmp_path: Path):
    """Verify atomic writing and loading of JSON and JSONL."""
    storage = StorageManager(base_data_dir=tmp_path)

    # Test JSON save & load
    test_data = {"act_id": "11", "act_name": "The Penal Code, 1860", "year": 1860}
    json_path = tmp_path / "processed" / "catalog.json"
    storage.save_json(json_path, test_data)

    loaded = storage.load_json(json_path)
    assert loaded == test_data

    # Test JSONL append
    jsonl_path = tmp_path / "processed" / "sections.jsonl"
    sec1 = {"section_id": "1", "title": "Sec 1"}
    sec2 = {"section_id": "2", "title": "Sec 2"}
    storage.append_jsonl(jsonl_path, sec1)
    storage.append_jsonl(jsonl_path, sec2)

    with open(jsonl_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 2
    assert lines[0] == sec1
    assert lines[1] == sec2


def test_live_client_fetch():
    """Verify that BDLawsClient can successfully fetch and decode the live chronological index."""
    client = BDLawsClient()
    html = client.get_html("laws-of-bangladesh-chronological-index.html")
    client.close()

    assert html is not None
    assert "<table" in html.lower()
    assert "1799" in html
