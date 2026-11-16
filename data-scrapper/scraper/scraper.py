"""Core Scraper orchestrator.

Coordinates discovery, parsing, extraction, storage, checkpoints, section-level retries,
and graceful interruption recovery.
"""

from typing import Dict, List, Optional
import logging
import signal
import sys
from tqdm import tqdm

import config
from scraper.client import BDLawsClient
from scraper.discovery import ActDiscovery
from scraper.extractor import DatasetExtractor
from scraper.parser import BDLawsParser
from scraper.storage import StorageManager
from scraper.validator import DataValidator

logger = logging.getLogger(__name__)


class BDLawsScraper:
    """Orchestrates end-to-end extraction workflow with section-level checkpointing."""

    def __init__(self, client: Optional[BDLawsClient] = None, storage: Optional[StorageManager] = None):
        self.client = client or BDLawsClient()
        self.storage = storage or StorageManager()
        self.discovery = ActDiscovery(self.client)
        self.parser = BDLawsParser()
        self.extractor = DatasetExtractor()
        self.validator = DataValidator()

        self._interrupted = False
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        logger.warning("Interrupt signal received (%s). Gracefully stopping after current request...", signum)
        self._interrupted = True

    def get_or_discover_catalog(self, force_refresh: bool = False) -> List[Dict[str, any]]:
        """Loads cached catalog or discovers from the portal."""
        if not force_refresh and config.CATALOG_FILE.exists():
            catalog = self.storage.load_json(config.CATALOG_FILE)
            if catalog:
                logger.info("Loaded %d Acts from existing catalog %s", len(catalog), config.CATALOG_FILE)
                return catalog

        catalog = self.discovery.discover_all_acts()
        self.storage.save_json(config.CATALOG_FILE, catalog)
        logger.info("Saved catalog with %d Acts to %s", len(catalog), config.CATALOG_FILE)
        return catalog

    def load_checkpoints(self) -> Dict[str, any]:
        """Loads checkpoint state with completed acts and failed sections."""
        default_state = {
            "completed_acts": {},
            "partially_completed_acts": {},
            "failed_acts": {},
        }
        return self.storage.load_json(config.CHECKPOINT_FILE, default=default_state)

    def save_checkpoints(self, checkpoints: Dict[str, any]) -> None:
        """Saves current checkpoint state atomically."""
        self.storage.save_json(config.CHECKPOINT_FILE, checkpoints)

    def scrape_single_act(
        self,
        act_info: Dict[str, any],
        language: Optional[str] = None,
        cached_sections: Optional[Dict[str, any]] = None,
    ) -> Optional[Dict[str, any]]:
        """Scrapes full content (metadata and all sections) of an Act with section-level tracking."""
        act_id = str(act_info["act_id"])
        act_lang = language or act_info.get("language", "en")
        act_url = f"{config.BASE_URL}/act-{act_id}.html"

        logger.info("Scraping Act %s (%s) [%s]", act_id, act_info.get("act_name"), act_lang)

        # 1. Fetch Act main page
        html = self.client.get_html(act_url, params={"lang": act_lang} if language else None)
        if not html:
            logger.error("Failed to fetch Act page for Act ID %s", act_id)
            return None

        self.storage.save_raw_html(act_id, None, html)
        parsed_act = self.parser.parse_act_page(html, act_url)
        section_links = parsed_act["sections"]

        section_records = []
        failed_sections = []
        already_scraped = cached_sections or {}

        for sec_ref in section_links:
            if self._interrupted:
                logger.info("Stopping section extraction for Act %s due to interrupt", act_id)
                break

            sec_url = sec_ref["section_url"]
            sec_id = sec_ref.get("section_id")

            # Check if section was previously fetched
            if sec_id and sec_id in already_scraped:
                section_records.append(already_scraped[sec_id])
                continue

            sec_html = self.client.get_html(sec_url, params={"lang": act_lang} if language else None)
            if not sec_html:
                logger.warning("Failed to fetch section %s", sec_url)
                failed_sections.append(sec_ref)
                continue

            self.storage.save_raw_html(act_id, sec_id, sec_html)
            sec_data = self.parser.parse_section_page(sec_html, sec_url)

            # Inherit chapter info from act page if missing
            if not sec_data.get("chapter_number"):
                sec_data["chapter_number"] = sec_ref.get("chapter_number")
            if not sec_data.get("chapter_title"):
                sec_data["chapter_title"] = sec_ref.get("chapter_title")

            sec_record = self.extractor.create_section_record(act_info, sec_data, act_lang)
            section_records.append(sec_record)
            if sec_id:
                already_scraped[sec_id] = sec_record

            # Append incrementally to global JSONL
            self.storage.append_jsonl(config.SECTIONS_JSONL_FILE, sec_record)

        # Assemble full Act document
        act_record = self.extractor.create_act_record(act_info, parsed_act, section_records, act_lang)
        self.storage.save_act_data(act_id, act_record)

        # Attach completion status
        act_record["_is_complete"] = (len(failed_sections) == 0 and not self._interrupted)
        act_record["_failed_sections"] = failed_sections
        return act_record

    def run(
        self,
        language: Optional[str] = None,
        limit: Optional[int] = None,
        act_id: Optional[str] = None,
        resume: bool = True,
        force_discover: bool = False,
    ) -> None:
        """Main execution entry point with incremental checkpoints and graceful interruption."""
        catalog = self.get_or_discover_catalog(force_refresh=force_discover)

        if act_id:
            catalog = [a for a in catalog if str(a["act_id"]) == str(act_id)]
            if not catalog:
                logger.error("Act ID %s not found in catalog", act_id)
                return

        if language:
            catalog = [a for a in catalog if a.get("language") == language]

        if limit and limit > 0:
            catalog = catalog[:limit]

        checkpoints = self.load_checkpoints() if resume else {
            "completed_acts": {},
            "partially_completed_acts": {},
            "failed_acts": {},
        }
        completed = checkpoints.setdefault("completed_acts", {})
        partial = checkpoints.setdefault("partially_completed_acts", {})
        failed = checkpoints.setdefault("failed_acts", {})

        logger.info("Starting scrape run. Target count: %d Acts", len(catalog))

        for act in tqdm(catalog, desc="Scraping Acts"):
            if self._interrupted:
                logger.warning("Gracefully exiting scrape loop. Progress has been saved in checkpoints.")
                break

            aid = str(act["act_id"])
            if resume and aid in completed:
                logger.debug("Skipping already completed Act %s", aid)
                continue

            result = self.scrape_single_act(act, language=language)
            if result:
                if result.get("_is_complete"):
                    completed[aid] = {
                        "act_name": act.get("act_name"),
                        "sections_count": result.get("total_sections", 0),
                    }
                    if aid in partial:
                        del partial[aid]
                    if aid in failed:
                        del failed[aid]
                else:
                    partial[aid] = {
                        "act_name": act.get("act_name"),
                        "sections_count": result.get("total_sections", 0),
                        "failed_sections": result.get("_failed_sections", []),
                    }
            else:
                failed[aid] = act.get("act_name")

            checkpoints["completed_acts"] = completed
            checkpoints["partially_completed_acts"] = partial
            checkpoints["failed_acts"] = failed
            self.save_checkpoints(checkpoints)

        logger.info("Scraping loop finished.")
