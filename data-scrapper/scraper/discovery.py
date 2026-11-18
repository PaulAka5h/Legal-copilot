"""Discovery module for Bangladesh Laws portal.

Discovers all available Acts across chronological, volume, and alphabetical indexes.
Extracts core catalog metadata, handles deduplication, preserves source URLs,
and builds an authoritative Act catalog.
"""

from typing import Dict, List, Optional, Set
import logging
import re
import urllib.parse
from bs4 import BeautifulSoup

from scraper.client import BDLawsClient
import config

logger = logging.getLogger(__name__)


class ActDiscovery:
    """Discovers and catalogs Acts from the official Bangladesh Laws portal."""

    def __init__(self, client: Optional[BDLawsClient] = None):
        self.client = client or BDLawsClient()

    def parse_catalog_table(self, html: str, source_url: str) -> List[Dict[str, any]]:
        """Extracts structured Act metadata from an index table.

        Handles both chronological and volume index tables.
        Columns typically consist of:
        - Column 1: Act Title (containing <a href="/act-{id}.html">)
        - Column 2: Act/Regulation Number (Roman, Arabic, or Bengali numeral)
        - Column 3: Act Year (e.g. 1860, 2020)
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning("No catalog table found in HTML from %s", source_url)
            return []

        discovered = []
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue

            # Look for link matching /act-{id}.html
            act_link = row.find("a", href=re.compile(r"/act-(\d+)\.html"))
            if not act_link:
                continue

            href = act_link.get("href", "").strip()
            match = re.search(r"/act-(\d+)\.html", href)
            if not match:
                continue

            act_id = match.group(1)
            full_act_url = urllib.parse.urljoin(config.BASE_URL, href)
            title = act_link.get_text(" ", strip=True)

            act_number = None
            act_year = None
            if len(cells) >= 3:
                act_number_raw = cells[1].get_text(strip=True)
                act_year_raw = cells[2].get_text(strip=True)
                act_number = act_number_raw if act_number_raw else None
                act_year = act_year_raw if act_year_raw else None

            # Detect language of title (Bengali script vs Latin)
            has_bangla = any("\u0980" <= char <= "\u09ff" for char in title)
            language = "bn" if has_bangla else "en"

            act_entry = {
                "act_id": act_id,
                "act_name": title,
                "act_number": act_number,
                "act_year": act_year,
                "language": language,
                "source_url": full_act_url,
                "discovered_from": source_url,
            }
            discovered.append(act_entry)

        logger.debug("Parsed %d Acts from table at %s", len(discovered), source_url)
        return discovered

    def discover_chronological_index(self, url: str = config.CHRONOLOGICAL_INDEX_URL) -> List[Dict[str, any]]:
        """Parses the master chronological index table."""
        logger.info("Fetching chronological index from %s", url)
        html = self.client.get_html(url)
        if not html:
            logger.error("Failed to retrieve chronological index HTML")
            return []

        return self.parse_catalog_table(html, source_url=url)

    def discover_volume_indexes(self, max_volumes: int = 58) -> List[Dict[str, any]]:
        """Traverses volume-wise indexes (/volume-1.html to /volume-58.html)."""
        logger.info("Checking volume-wise indexes (1 to %d)...", max_volumes)
        all_volume_acts = []
        for vol_num in range(1, max_volumes + 1):
            vol_url = f"{config.BASE_URL}/volume-{vol_num}.html"
            html = self.client.get_html(vol_url)
            if not html:
                continue
            acts = self.parse_catalog_table(html, source_url=vol_url)
            all_volume_acts.extend(acts)
        logger.info("Discovered %d total Act entries across volume indexes", len(all_volume_acts))
        return all_volume_acts

    def discover_all_acts(self, include_volumes: bool = False) -> List[Dict[str, any]]:
        """Traverses indexes and returns deduplicated list of all Acts."""
        acts_by_id: Dict[str, Dict[str, any]] = {}

        # 1. Primary master index: Chronological Index (contains all 1685 Acts)
        chrono_acts = self.discover_chronological_index()
        for act in chrono_acts:
            acts_by_id[act["act_id"]] = act

        # 2. Volume-wise indexes if requested
        if include_volumes:
            volume_acts = self.discover_volume_indexes()
            for act in volume_acts:
                aid = act["act_id"]
                if aid not in acts_by_id:
                    acts_by_id[aid] = act
                else:
                    # Enrich missing fields if any
                    for key in ["act_number", "act_year"]:
                        if not acts_by_id[aid].get(key) and act.get(key):
                            acts_by_id[aid][key] = act[key]

        # Sort catalog deterministically: numeric act_id if possible
        sorted_acts = sorted(
            acts_by_id.values(),
            key=lambda x: int(x["act_id"]) if x["act_id"].isdigit() else x["act_id"],
        )
        logger.info("Total unique Acts cataloged: %d", len(sorted_acts))
        return sorted_acts
