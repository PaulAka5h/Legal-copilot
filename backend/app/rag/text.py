"""Unicode handling shared by ingestion, embedding, search, and citation checks.

All stored legal text, search queries, and text sent to the embedder are NFC.
NFC keeps ZWJ (U+200D) and ZWNJ (U+200C), which change Bangla conjunct
rendering, and they are never stripped here.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")  # Unicode whitespace only; ZWJ/ZWNJ are format chars, not spaces


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def normalize_for_match(text: str) -> str:
    """NFC plus collapsed whitespace, for comparing a quote against stored text."""
    return _WHITESPACE.sub(" ", nfc(text)).strip()


def quote_in_text(quote: str, text: str) -> bool:
    """True when the normalized quote is a substring of the normalized stored text."""
    needle = normalize_for_match(quote)
    return bool(needle) and needle in normalize_for_match(text)
