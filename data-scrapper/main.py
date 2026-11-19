"""CLI Interface for Bangladesh Laws Scraper."""

import argparse
import json
import logging
import sys
from pathlib import Path

import config
from scraper.client import BDLawsClient
from scraper.export import export_sections
from scraper.scraper import BDLawsScraper
from scraper.storage import StorageManager
from scraper.validator import DataValidator


def setup_logging(verbose: bool = False):
    """Sets up console and file logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Bangladesh Laws Scraper — High-accuracy legal data extractor for Legal AI / RAG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--language", choices=["en", "bn"], help="Target language to scrape (en or bn)")
    parser.add_argument("--limit", type=int, help="Limit total number of Acts to scrape")
    parser.add_argument("--act-id", type=str, help="Scrape a specific Act by ID (e.g. 11 for Penal Code)")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from last checkpoint (default: True)")
    parser.add_argument("--no-resume", dest="resume", action="store_false", help="Do not resume, scrape from start")
    parser.add_argument("--discover", action="store_true", help="Run catalog discovery only and output catalog.json")
    parser.add_argument("--validate", action="store_true", help="Run validation checks on existing extracted data")
    parser.add_argument("--report", action="store_true", help="Generate quality and statistics report")
    parser.add_argument(
        "--export-sections", action="store_true",
        help="Rebuild sections.jsonl from data/processed/acts/ (no network); invalid records go to a report",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.export_sections:
        summary = export_sections(config.ACTS_DIR, config.SECTIONS_JSONL_FILE, config.EXPORT_REPORT_FILE)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"[✓] Rejects and duplicates listed in {config.EXPORT_REPORT_FILE}")
        return

    client = BDLawsClient()
    storage = StorageManager()
    scraper = BDLawsScraper(client=client, storage=storage)

    try:
        if args.discover:
            print("[*] Running website discovery across indexes...")
            catalog = scraper.get_or_discover_catalog(force_refresh=True)
            print(f"[✓] Successfully discovered and saved {len(catalog)} Acts into {config.CATALOG_FILE}")
            return

        if args.validate or args.report:
            print("[*] Performing validation on extracted records...")
            records = []
            if config.SECTIONS_JSONL_FILE.exists():
                with open(config.SECTIONS_JSONL_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            records.append(json.loads(line))
            
            catalog = storage.load_json(config.CATALOG_FILE, default=[])
            report = DataValidator.generate_report(records, discovered_acts_count=len(catalog))
            storage.save_json(config.VALIDATION_REPORT_FILE, report)

            print(json.dumps(report, indent=2, ensure_ascii=False))
            print(f"[✓] Report saved to {config.VALIDATION_REPORT_FILE}")
            return

        # Standard scraping run
        scraper.run(
            language=args.language,
            limit=args.limit,
            act_id=args.act_id,
            resume=args.resume,
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()
