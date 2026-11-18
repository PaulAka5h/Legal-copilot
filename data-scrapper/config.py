"""Configuration settings for Bangladesh Laws Scraper."""

from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
FAILED_DATA_DIR = DATA_DIR / "failed"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

# Ensure all essential directories exist
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, FAILED_DATA_DIR, REPORTS_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# File Paths
CATALOG_FILE = PROCESSED_DATA_DIR / "catalog.json"
SECTIONS_JSONL_FILE = PROCESSED_DATA_DIR / "sections.jsonl"
ACTS_DIR = PROCESSED_DATA_DIR / "acts"
ACTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = PROCESSED_DATA_DIR / "checkpoints.json"
FAILED_RECORDS_FILE = FAILED_DATA_DIR / "failed_records.json"
VALIDATION_REPORT_FILE = REPORTS_DIR / "validation_report.json"

# Network & Scraping Settings
BASE_URL = "https://bdlaws.minlaw.gov.bd"
CHRONOLOGICAL_INDEX_URL = f"{BASE_URL}/laws-of-bangladesh-chronological-index.html"
ALPHABETICAL_INDEX_URL = f"{BASE_URL}/laws-of-bangladesh-alphabetical-index.html"

REQUEST_TIMEOUT = 60  # seconds
REQUEST_DELAY = 1.2  # seconds between requests to avoid server-side rate limit throttling
MAX_RETRIES = 5
BACKOFF_FACTOR = 2.0

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
    "Connection": "keep-alive",
}

# Logging Configuration
LOG_FILE = LOGS_DIR / "scraper.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_LEVEL = "INFO"
