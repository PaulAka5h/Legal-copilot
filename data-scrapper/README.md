# Bangladesh Laws Scraper — Legal RAG Dataset Builder

A production-grade, modular, and resilient web data extraction pipeline built in Python to extract Bangladesh's official legal corpus from [bdlaws.minlaw.gov.bd](https://bdlaws.minlaw.gov.bd/laws-of-bangladesh.html).

The extracted legal dataset preserves the full legal hierarchy (Acts, Chapters, Sections, Subsections, Provs/Explanations, and Footnotes) in both **English (`en`)** and **Bangla (`bn`)**, formatted as structured JSON and JSONL documents ready for Legal AI / Copilot RAG pipelines (compatible with `multilingual-e5-base`, Qdrant, hybrid sparse/dense retrieval, and cross-encoder rerankers).

---

## 1. Project Overview & Features

- **Automated Catalog Discovery:** Crawls chronological and volume indexes, discovering and cataloging **1,685 Acts and Regulations** from 1799 to the present.
- **Hierarchical Legal Extraction:** Retains chapter groupings, section heads, subsection clause markers (`(1)`, `(১)`, `(a)`, `(ক)`), and official enactment dates.
- **Bilingual & Unicode Preserving:** Full native UTF-8 support for both Bengali and English scripts with automated script detection (`\u0980-\u09ff`).
- **Resilient Network Client:** Session reuse, polite rate-limiting, exponential backoff retries, and automatic multi-tier decoding handling Apache/Tomcat UTF-16 / UTF-8 header quirks without character corruption.
- **Incremental Scraping & Resumption:** Granular 3-tier checkpoints (`completed_acts`, `partially_completed_acts`, `failed_acts`) with atomic writes to safely resume after interruptions (SIGINT/SIGTERM) without duplicate downloads.
- **RAG-Ready Schemas:** Deterministic document IDs (`bd-act-{id}-sec-{num}-{lang}`), section chunk boundaries, SHA-256 content hashes, and official URL provenance.
- **Data Quality & Validation:** Built-in validator checking for empty legal texts, missing fields, Unicode replacement corruption (`\ufffd`), unescaped HTML leaks, and duplicates.

---

## 2. Technology Stack

- **Python 3.11+**
- **Requests** (HTTP transport with session pooling & custom retry adapters)
- **BeautifulSoup4 & lxml** (High-performance DOM parsing)
- **tqdm** (Real-time progress bars)
- **Pytest** (Comprehensive test suite with offline fixtures)

---

## 3. Project Architecture

```text
data-scrapper/
├── scraper/
│   ├── __init__.py           # Package indicator
│   ├── client.py             # Resilient HTTP client & charset decoding
│   ├── discovery.py          # Act catalog crawler & deduplication
│   ├── parser.py             # BeautifulSoup DOM parsers for Acts & Sections
│   ├── extractor.py          # RAG dataset normalizer & SHA256 hash generator
│   ├── storage.py            # Atomic file I/O for JSON, JSONL, & HTML caches
│   ├── validator.py          # Quality assurance & report generator
│   └── scraper.py            # Master workflow coordinator, checkpoints & SIGINT handler
├── data/
│   ├── raw/                  # Cached HTML source files for auditing
│   ├── processed/            # Primary output datasets
│   │   ├── acts/             # Full Act-level structured JSON documents
│   │   ├── catalog.json      # Master index of 1,685 Acts
│   │   ├── checkpoints.json  # Resumption & checkpoint state
│   │   └── sections.jsonl    # Section-level streaming dataset for RAG ingestion
│   ├── failed/               # Failed records & URLs for triage
│   └── reports/              # Data quality validation reports
├── logs/                     # Scraper runtime execution logs
├── tests/                    # Unit and integration tests
│   ├── fixtures/             # HTML test fixtures
│   ├── test_checkpoints.py   # Resumption & checkpoint tests
│   ├── test_discovery.py     # Index parsing tests
│   ├── test_extractor.py     # Dataset normalization tests
│   ├── test_parser.py        # DOM parser unit tests
│   ├── test_phase2.py        # Storage & client tests
│   └── test_validator.py     # Data validation & corruption tests
├── config.py                 # Central configuration settings
├── main.py                   # Command-line interface (CLI)
├── requirements.txt          # Python dependencies
├── pytest.ini                # Pytest configuration
├── .gitignore                # Git ignore rules
└── README.md                 # Project documentation
```

---

## 4. Installation & Setup

```bash
# 1. Clone repository and navigate to folder
cd /home/arafath/Projects/data-scrapper

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install required packages
pip install -r requirements.txt
```

---

## 5. Usage & CLI Commands

### 5.1 Discover Acts Only
Traverse the official indexes, deduplicate, and generate `data/processed/catalog.json`:
```bash
python main.py --discover
```

### 5.2 Scrape Specific Act
Extract a specific law by Act ID (e.g. Act 11 - *The Penal Code, 1860* or Act 1306 - *বাংলাদেশ ট্যারিফ কমিশন আইন*):
```bash
# English Act
python main.py --act-id 11 --language en

# Bangla Act
python main.py --act-id 1306 --language bn
```

### 5.3 Batch Scraping with Limit
Scrape a small batch of Acts for testing or quick evaluations:
```bash
python main.py --language en --limit 5
```

### 5.4 Scrape Entire Language Corpus
```bash
# Scrape all English acts
python main.py --language en

# Scrape all Bangla acts
python main.py --language bn
```

### 5.5 Resume Interrupted Scraping
Scraping is incremental by default. If interrupted (via Ctrl+C or network failure), resume immediately:
```bash
python main.py --language en --resume
```
*(To force scraping from the beginning, use `--no-resume`).*

### 5.6 Data Validation & Quality Audit Report
Validate all scraped sections, checking for missing fields, encoding corruption, and duplicates:
```bash
python main.py --report
```
The report is saved to `data/reports/validation_report.json`.

---

## 6. Dataset Schema & Output Format

### 6.1 Section Record (`data/processed/sections.jsonl`)
Each line is an independent, valid JSON record designed for RAG ingestion:
```json
{
  "document_id": "bd-act-11-sec-53-en",
  "act_id": "11",
  "act_name": "The Penal Code, 1860",
  "act_number": "XLV",
  "act_year": "1860",
  "language": "en",
  "chapter_number": "Chapter III",
  "chapter_title": "OF PUNISHMENTS",
  "section_number": "53",
  "section_title": "Punishments",
  "section_content": "The punishments to which offenders are liable under the provisions of this Code are,-\nFirstly,- Death;\nSecondly,- [Imprisonment for life]...",
  "subsections": [
    {
      "subsection_identifier": "(1)",
      "text": "Rigorous, that is, with hard labour;"
    },
    {
      "subsection_identifier": "(2)",
      "text": "Simple;"
    }
  ],
  "source_url": "https://bdlaws.minlaw.gov.bd/act-11/section-2188.html",
  "source_website": "bdlaws.minlaw.gov.bd",
  "enactment_date": "6th October, 1860",
  "scraped_at": "2026-11-16T20:07:15.403263+00:00",
  "content_hash": "2c729eea5ad9f3ffe7a0c476d766b5a3c15a42665ac763aec60dfb26e8f9d457"
}
```

### 6.2 Full Act Document (`data/processed/acts/act_{id}.json`)
Contains the complete Act hierarchy with nested section records for legal document viewing.

---

## 7. Running Unit Tests

Run the test suite using `pytest`:
```bash
pytest -v
```
All 11 unit and integration tests run offline against HTML fixtures without hitting the live website.

---

## 8. Legal Data Source & Attribution

- **Official Source:** [Ministry of Law, Justice and Parliamentary Affairs, Bangladesh](https://bdlaws.minlaw.gov.bd)
- **Data Policy:** Crawled strictly respecting server load constraints with polite delays (`0.5s`), persistent sessions, and backoff retries.
