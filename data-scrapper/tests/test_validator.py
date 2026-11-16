"""Unit tests for DataValidator."""

from scraper.validator import DataValidator


def test_validator_detects_empty_content():
    bad_record = {
        "document_id": "test-doc-1",
        "act_id": "1",
        "act_name": "Test Act",
        "section_content": "",
        "source_url": "http://example.com",
        "content_hash": "hash",
    }
    issues = DataValidator.validate_section_record(bad_record)
    assert "Empty section_content" in issues


def test_validator_detects_unicode_corruption():
    corrupted_record = {
        "document_id": "test-doc-2",
        "act_id": "2",
        "act_name": "Corrupted Act",
        "section_content": "The law states \ufffd that offenders...",
        "source_url": "http://example.com",
        "content_hash": "hash",
    }
    issues = DataValidator.validate_section_record(corrupted_record)
    assert any("Unicode replacement" in i for i in issues)


def test_validator_valid_record():
    good_record = {
        "document_id": "test-doc-3",
        "act_id": "3",
        "act_name": "Valid Act",
        "section_content": "Every person shall be liable to punishment.",
        "source_url": "http://example.com",
        "content_hash": "abc12345",
    }
    issues = DataValidator.validate_section_record(good_record)
    assert len(issues) == 0
