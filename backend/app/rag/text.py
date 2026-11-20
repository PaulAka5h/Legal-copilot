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


# Curated Bangla function words (sadhu and cholito forms) removed from full-text
# queries, like English stopwords. Legal content words (ধারা, আইন, আদালত, মামলা,
# শাস্তি, অপরাধ, ...) are deliberately absent. Stored NFC so they match lexemes.
BANGLA_STOPWORDS: frozenset[str] = frozenset(
    nfc(word)
    for word in (
        # conjunctions and particles
        "এবং", "ও", "বা", "অথবা", "কিন্তু", "তবে", "যদি", "তবুও", "যে", "যা", "যাহা", "যেমন",
        "কি", "কী", "না", "নয়", "নহে", "ই", "তো", "ত", "হয়ত", "বরং",
        # pronouns and determiners
        "এই", "ঐ", "ওই", "সেই", "এ", "সে", "তা", "তাহা", "তাহার", "তার", "তাহারা", "তারা",
        "তাহাদের", "তাদের", "তিনি", "তাঁহার", "তাঁর", "আমি", "আমার", "আমরা", "আমাদের",
        "আপনি", "আপনার", "যিনি", "যাহার", "যার", "কোন", "কোনো", "কোনও", "সকল", "সব",
        "প্রত্যেক", "একটি", "একজন", "এক", "টি", "এর", "উক্ত",
        # postpositions
        "জন্য", "জন্যে", "সহিত", "সাথে", "সঙ্গে", "হইতে", "থেকে", "থেকেও", "পর্যন্ত", "মধ্যে",
        "উপর", "দ্বারা", "কর্তৃক", "প্রতি", "নিকট", "কাছে", "পরে", "পূর্বে", "আগে", "বিষয়ে",
        "সম্পর্কে", "অনুযায়ী", "অনুসারে", "মতে", "ব্যতীত", "ছাড়া",
        # auxiliaries and common verb forms
        "হয়", "হইবে", "হবে", "হইয়াছে", "হয়েছে", "হইল", "হলো", "হল", "ছিল", "আছে", "থাকে",
        "থাকিবে", "করা", "করে", "করিয়া", "করিবে", "করবে", "করিতে", "করতে", "হইতেছে", "হচ্ছে",
        "বলিয়া", "বলে", "দিয়া", "দিয়ে",
        # question words
        "কেন", "কিভাবে", "কীভাবে", "কোথায়", "কখন", "কত",
    )
)


def quote_in_text(quote: str, text: str) -> bool:
    """True when the normalized quote is a substring of the normalized stored text."""
    needle = normalize_for_match(quote)
    return bool(needle) and needle in normalize_for_match(text)
