"""Normalizer utility for English and Bengali legal numerals and queries."""

import re
from typing import Optional

# Mapping between Bengali digits (০-৯) and English digits (0-9)
BN_TO_EN_DIGITS = {
    "০": "0",
    "১": "1",
    "২": "2",
    "৩": "3",
    "৪": "4",
    "৫": "5",
    "৬": "6",
    "৭": "7",
    "৮": "8",
    "৯": "9",
}

EN_TO_BN_DIGITS = {v: k for k, v in BN_TO_EN_DIGITS.items()}


def normalize_to_en_digits(text: str) -> str:
    """Replaces Bengali digits in text with English digits."""
    return "".join(BN_TO_EN_DIGITS.get(char, char) for char in text)


def normalize_to_bn_digits(text: str) -> str:
    """Replaces English digits in text with Bengali digits."""
    return "".join(EN_TO_BN_DIGITS.get(char, char) for char in text)


def extract_section_numbers(query: str) -> list[str]:
    """Extracts candidate section identifiers from either English or Bengali legal text.

    Examples:
    - 'Section 302' -> ['302']
    - 'ধারা ৩০২' -> ['302', '৩০২']
    - 'Section 138(1)(a)' -> ['138', '138(1)(a)']
    - 'ধারা ৪২০' -> ['420', '৪২০']
    """
    clean_query = query.strip()
    en_clean = normalize_to_en_digits(clean_query)

    candidates = set()

    # Regex matches: section/sec/ধারা/দফা followed by number and optional subclauses e.g. 138(1)(a)
    patterns = [
        r"(?:section|sec\.?|s\.)\s*([0-9]+[A-Za-z]?(?:\([0-9a-zA-Z]+\))*)",
        r"(?:ধারা|দফা)\s*([0-9]+[A-Za-z]?(?:\([0-9a-zA-Z]+\))*)",
        r"(?:ধারা|দফা)\s*([০-৯]+[ক-ঞ]?(?:\([০-৯a-zA-Zক-ঞ]+\))*)",
    ]

    for pat in patterns:
        for m in re.finditer(pat, clean_query, re.IGNORECASE):
            raw_match = m.group(1)
            en_num = normalize_to_en_digits(raw_match)
            bn_num = normalize_to_bn_digits(en_num)
            candidates.add(en_num)
            candidates.add(bn_num)
            # Add base section number if subclauses are present (e.g., '138' from '138(1)')
            base_en = re.split(r"[\(\[]", en_num)[0]
            if base_en:
                candidates.add(base_en)
                candidates.add(normalize_to_bn_digits(base_en))

    # Also search en_clean
    for pat in patterns[:2]:
        for m in re.finditer(pat, en_clean, re.IGNORECASE):
            en_num = m.group(1)
            candidates.add(en_num)
            candidates.add(normalize_to_bn_digits(en_num))
            base_en = re.split(r"[\(\[]", en_num)[0]
            if base_en:
                candidates.add(base_en)
                candidates.add(normalize_to_bn_digits(base_en))

    return sorted(list(candidates))
