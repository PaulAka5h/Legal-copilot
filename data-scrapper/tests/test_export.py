"""Tests for rebuilding sections.jsonl from Act files. SAMPLE_DATA_NOT_REAL_LAW."""

import json

from scraper.export import export_sections


def _section(doc_id, content, lang="bn", url="http://example.invalid/act-1/section-1.html"):
    return {
        "document_id": doc_id,
        "act_id": doc_id.split("-")[2],
        "act_name": "SAMPLE_DATA_NOT_REAL_LAW আইন",
        "language": lang,
        "section_number": "১",
        "section_content": content,
        "source_url": url,
        "content_hash": "h",
    }


def _write_act(acts_dir, act_id, sections):
    path = acts_dir / f"act_{act_id}.json"
    path.write_text(json.dumps({"act_id": act_id, "sections": sections}, ensure_ascii=False), encoding="utf-8")


def test_export_orders_validates_dedupes_and_keeps_bangla(tmp_path):
    acts = tmp_path / "acts"
    acts.mkdir()
    bangla = "ধারা ১। SAMPLE_DATA_NOT_REAL_LAW নমুনা পাঠ।"
    _write_act(acts, "10", [_section("bd-act-10-sec-1-bn", bangla)])
    _write_act(acts, "2", [
        _section("bd-act-2-sec-1-bn", bangla),
        _section("bd-act-2-sec-1-bn", bangla),
        _section("bd-act-2-sec-1-bn", bangla, url="http://example.invalid/act-2/section-77.html"),
        _section("bd-act-2-sec-2-bn", ""),
    ])
    out = tmp_path / "sections.jsonl"
    report = tmp_path / "report.json"

    summary = export_sections(acts, out, report)

    lines = out.read_text(encoding="utf-8").splitlines()
    ids = [json.loads(line)["document_id"] for line in lines]
    # numeric act order; same ID with a different URL is kept under a new ID
    assert ids == ["bd-act-2-sec-1-bn", "bd-act-2-sec-1-bn-s77", "bd-act-10-sec-1-bn"]
    assert json.loads(lines[0])["section_content"] == bangla  # UTF-8 round-trip
    assert summary["written"] == 3
    assert summary["renamed_id_count"] == 1
    assert summary["duplicate_count"] == 1
    assert summary["rejected_count"] == 1
    rep = json.loads(report.read_text(encoding="utf-8"))
    assert rep["rejected"][0]["document_id"] == "bd-act-2-sec-2-bn"
    assert "Empty section_content" in rep["rejected"][0]["issues"]
    assert set(rep["rejected"][0]) == {"document_id", "act_id", "language", "issues"}  # no legal text
