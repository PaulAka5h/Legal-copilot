"""Unit tests for DatasetExtractor and schema conformity."""

from scraper.extractor import DatasetExtractor


def test_create_section_record():
    act_info = {
        "act_id": "11",
        "act_name": "The Penal Code, 1860",
        "act_number": "XLV",
        "act_year": "1860",
        "source_url": "https://bdlaws.minlaw.gov.bd/act-11.html",
    }
    section_data = {
        "section_number": "53",
        "section_title": "Punishments",
        "section_content": "The punishments to which offenders are liable...",
        "chapter_number": "Chapter III",
        "chapter_title": "OF PUNISHMENTS",
        "subsections": [{"subsection_identifier": "(1)", "text": "Death"}],
        "source_url": "https://bdlaws.minlaw.gov.bd/act-11/section-2188.html",
    }

    record = DatasetExtractor.create_section_record(act_info, section_data, language="en")

    assert record["document_id"] == "bd-act-11-sec-53-en"
    assert record["act_id"] == "11"
    assert record["language"] == "en"
    assert record["chapter_number"] == "Chapter III"
    assert record["section_number"] == "53"
    assert len(record["subsections"]) == 1
    assert record["content_hash"] is not None
    assert len(record["content_hash"]) == 64
