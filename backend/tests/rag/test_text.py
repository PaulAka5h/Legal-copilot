"""Unicode normalization and header rules. SAMPLE_DATA_NOT_REAL_LAW."""

import unicodedata

from app.rag.ingest.chunking import section_header, title_ends_with_year
from app.rag.text import nfc, normalize_for_match, quote_in_text

ZWJ, ZWNJ = "‍", "‌"
# Same words, two encodings each:
RRA = ("ড়", "ড়")  # ড় precomposed vs ড + nukta
YYA = ("য়", "য়")  # য় precomposed vs য + nukta
O_SIGN = ("ো", "ো")  # ো single vs ে + া


def word(rra: str, yya: str, o: str) -> str:
    return f"প{rra}া ক{o}নো স{yya}"


def test_bangla_variants_normalize_to_one_form_and_match():
    stored = f"SAMPLE_DATA_NOT_REAL_LAW ধারা ১। {word(RRA[0], YYA[0], O_SIGN[1])} হইবে।"
    for rra in RRA:
        for yya in YYA:
            for o in O_SIGN:
                quote = word(rra, yya, o)
                assert nfc(quote) == nfc(word(RRA[1], YYA[1], O_SIGN[0]))
                assert quote_in_text(quote, stored)
    assert unicodedata.is_normalized("NFC", nfc(stored))


def test_zwj_and_zwnj_are_kept_not_stripped():
    text = f"র{ZWJ}্য SAMPLE ক{ZWNJ}্ষ"
    assert ZWJ in nfc(text) and ZWNJ in nfc(text)
    assert ZWJ in normalize_for_match(text) and ZWNJ in normalize_for_match(text)
    assert not quote_in_text("র্য", text)  # a ZWJ difference is a real difference


def test_quote_matching_collapses_whitespace_and_rejects_empty():
    assert quote_in_text("SAMPLE   ধারা\n১", "x SAMPLE ধারা ১ y")
    assert not quote_in_text("   ", "anything")
    assert not quote_in_text("absent", "SAMPLE text")


def test_header_year_added_only_when_title_lacks_it():
    assert title_ends_with_year("SAMPLE Act, 1850", "1850")
    assert title_ends_with_year("SAMPLE আইন, ১৯৮০", "১৯৮০")
    assert title_ends_with_year("SAMPLE আইন, ১৯৮০", "1980")  # mixed digit systems
    assert title_ends_with_year("SAMPLE Ordinance, 1985 (No. X of 1985)", "1985")
    assert not title_ends_with_year("SAMPLE Act", "1850")

    assert section_header("SAMPLE Act, 1850", "1850", "1", "Title") == "SAMPLE Act, 1850 — Section 1: Title\n"
    assert section_header("SAMPLE Act", "1850", "1", "Title") == "SAMPLE Act (1850) — Section 1: Title\n"
    assert section_header("SAMPLE আইন, ১৯৮০", "১৯৮০", "১", None) == "SAMPLE আইন, ১৯৮০ — Section ১\n"
