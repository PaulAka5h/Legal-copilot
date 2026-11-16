"""Data quality validation and reporting module for Bangladesh Laws dataset."""

from typing import Any, Dict, List
import logging
import re

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates extracted legal records against quality and consistency standards."""

    @staticmethod
    def validate_section_record(record: Dict[str, Any]) -> List[str]:
        """Checks a section record for completeness and integrity issues."""
        issues = []

        if not record.get("document_id"):
            issues.append("Missing document_id")

        if not record.get("act_id"):
            issues.append("Missing act_id")

        if not record.get("act_name"):
            issues.append("Empty act_name")

        content = record.get("section_content", "")
        if not content or len(content.strip()) == 0:
            issues.append("Empty section_content")

        if not record.get("source_url"):
            issues.append("Missing source_url")

        if not record.get("content_hash"):
            issues.append("Missing content_hash")

        # Check for garbled unicode replacement chars
        if "\ufffd" in content:
            issues.append("Contains Unicode replacement characters (encoding corruption)")

        # Verify language metadata consistency with content
        lang = record.get("language")
        has_bangla = any("\u0980" <= char <= "\u09ff" for char in content)
        if lang == "bn" and not has_bangla and len(content) > 100:
            issues.append("Language marked as 'bn' but content has no Bengali script characters")
        elif lang == "en" and has_bangla and len(content) > 100:
            # Note: minor footnotes might cite Bangla, but if majority is Bangla in English act, flag warning
            bangla_chars = sum(1 for c in content if "\u0980" <= c <= "\u09ff")
            if bangla_chars / len(content) > 0.5:
                issues.append("Language marked as 'en' but text is predominantly Bengali")

        # Check for leftover raw HTML tags in section_content
        if re.search(r"<[a-zA-Z\/][^>]*>", content):
            issues.append("Contains unescaped HTML tags in section_content")

        return issues

    @classmethod
    def generate_report(
        cls,
        section_records: List[Dict[str, Any]],
        discovered_acts_count: int = 0,
        checkpoints: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Generates comprehensive scraping and data quality report."""
        total_sections = len(section_records)
        unique_doc_ids = set()
        duplicates = 0
        empty_content = 0
        bn_count = 0
        en_count = 0
        acts_present = set()
        all_issues = []

        for r in section_records:
            doc_id = r.get("document_id")
            if doc_id in unique_doc_ids:
                duplicates += 1
            else:
                unique_doc_ids.add(doc_id)

            if not r.get("section_content"):
                empty_content += 1

            lang = r.get("language")
            if lang == "bn":
                bn_count += 1
            else:
                en_count += 1

            act_id = r.get("act_id")
            if act_id:
                acts_present.add(act_id)

            issues = cls.validate_section_record(r)
            if issues:
                all_issues.append({"document_id": doc_id, "issues": issues})

        ckpt = checkpoints or {}
        completed_acts_count = len(ckpt.get("completed_acts", acts_present))
        partially_acts_count = len(ckpt.get("partially_completed_acts", {}))
        failed_acts_count = len(ckpt.get("failed_acts", {}))

        report = {
            "total_discovered_acts": discovered_acts_count,
            "successfully_scraped_acts": completed_acts_count,
            "partially_scraped_acts": partially_acts_count,
            "failed_acts": failed_acts_count,
            "total_extracted_sections": total_sections,
            "bangla_sections_count": bn_count,
            "english_sections_count": en_count,
            "duplicate_records_count": duplicates,
            "empty_content_count": empty_content,
            "total_validation_warnings": len(all_issues),
            "sample_issues": all_issues[:15],
        }
        return report
