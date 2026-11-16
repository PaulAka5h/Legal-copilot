"""Extractor module: converts parsed raw records into standardized schema records."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class DatasetExtractor:
    """Standardizes parsed Act and Section data into RAG-ready records."""

    @staticmethod
    def compute_hash(text: str) -> str:
        """Calculates deterministic SHA256 hash of text content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def create_section_record(
        cls,
        act_info: Dict[str, Any],
        section_data: Dict[str, Any],
        language: str,
    ) -> Dict[str, Any]:
        """Transforms extracted Section into uniform Legal Dataset Record."""
        act_id = str(act_info.get("act_id", ""))
        sec_num = section_data.get("section_number") or ""
        sec_id_slug = f"sec-{sec_num}" if sec_num else DatasetExtractor.compute_hash(section_data.get("source_url", ""))[:8]
        document_id = f"bd-act-{act_id}-{sec_id_slug}-{language}"

        content = section_data.get("section_content", "").strip()
        content_hash = cls.compute_hash(content) if content else None

        record = {
            "document_id": document_id,
            "act_id": act_id,
            "act_name": act_info.get("act_name", ""),
            "act_number": act_info.get("act_number"),
            "act_year": act_info.get("act_year"),
            "language": language,
            "chapter_number": section_data.get("chapter_number") or act_info.get("chapter_number"),
            "chapter_title": section_data.get("chapter_title") or act_info.get("chapter_title"),
            "section_number": section_data.get("section_number"),
            "section_title": section_data.get("section_title"),
            "section_content": content,
            "subsections": section_data.get("subsections", []),
            "source_url": section_data.get("source_url", ""),
            "source_website": "bdlaws.minlaw.gov.bd",
            "enactment_date": section_data.get("enactment_date") or act_info.get("enactment_date"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash,
        }
        return record

    @classmethod
    def create_act_record(
        cls,
        act_info: Dict[str, Any],
        parsed_act: Dict[str, Any],
        section_records: list,
        language: str,
    ) -> Dict[str, Any]:
        """Builds complete Act-level structured document."""
        return {
            "act_id": str(act_info.get("act_id", "")),
            "act_name": parsed_act.get("act_title") or act_info.get("act_name"),
            "act_number": act_info.get("act_number"),
            "act_year": act_info.get("act_year"),
            "language": language,
            "enactment_date": parsed_act.get("enactment_date"),
            "source_url": act_info.get("source_url"),
            "total_sections": len(section_records),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "sections": section_records,
        }
