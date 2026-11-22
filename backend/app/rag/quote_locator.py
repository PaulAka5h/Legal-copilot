"""Locate a model's quote inside the stored chunk text and return the EXACT source span.

The verifier never stores the model's wording. It stores `chunk_text[start:end]`, so a
verified quote is always an exact substring of the chunk (Rule 1, no invented text).
Steps, in order (the first that succeeds wins):

1. exact:      the quote is a substring of the chunk as stored (NFC).
2. normalized: equal after normalization: NFC, whitespace collapsed, curly quotes,
               dashes and the danda unified (। ॥ | -> ।; no space before a danda),
               ZWJ/ZWNJ ignored, case ignored (English). A hyphen at a line end
               ("dis-\nhonoured") is tried as written, joined with its hyphen
               ("উপ-ধারা") and joined without it ("dishonoured").
3. fuzzy:      a word-aligned window of the normalized chunk with
               difflib ratio >= FUZZY_MIN_RATIO; only for quotes of at least
               FUZZY_MIN_CHARS characters and FUZZY_MIN_WORDS words.

`segments()` numbers a chunk's sentences/lines for the prompt (quote_ref); a ref is
only a hint about where to look first, never a substitute for matching.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

FUZZY_MIN_RATIO = 0.9
FUZZY_MIN_CHARS = 20
FUZZY_MIN_WORDS = 4

_MAP = {
    **{c: '"' for c in "“”„‟″«»"},
    **{c: "'" for c in "‘’‚‛′"},
    **{c: "-" for c in "‐‑‒–—―−"},
    "॥": "।", "|": "।",
}
_DROP = {"‌", "‍", "﻿", "­"}  # ZWNJ, ZWJ, BOM, soft hyphen
_SEGMENT_END = re.compile(r"(?<=[.;?!।॥])\s+|\n+")  # not ":" (statute headers)


@dataclass(frozen=True)
class Located:
    text: str  # exact chunk_text[start:end]
    start: int
    end: int
    method: str  # exact | normalized | fuzzy
    ratio: float = 1.0


def _word_char(ch: str) -> bool:
    """Letters, digits, and combining marks (Bangla vowel signs are marks, not letters)."""
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def _line_end_hyphen(value: str, i: int) -> int | None:
    """If value[i] is a hyphen that ends a line inside a word, the index after the line break."""
    if i == 0 or not _word_char(value[i - 1]):
        return None
    j = i + 1
    while j < len(value) and value[j] in " \t\r":
        j += 1
    if j >= len(value) or value[j] != "\n":
        return None
    j += 1
    while j < len(value) and value[j].isspace():
        j += 1
    return j if j < len(value) and _word_char(value[j]) else None


HyphenMode = str  # "as_is" | "keep" (drop the line break) | "join" (drop hyphen and line break)
HYPHEN_MODES: tuple[HyphenMode, ...] = ("as_is", "keep", "join")


def _normalize(value: str, hyphens: HyphenMode = "as_is") -> tuple[str, list[int]]:
    """Normalized text plus, for each normalized char, the index of its source char."""
    out: list[str] = []
    index: list[int] = []
    i = 0
    while i < len(value):
        ch = value[i]
        i += 1
        if ch in _DROP:
            continue
        ch = _MAP.get(ch, ch).lower()
        if ch == "-" and hyphens != "as_is":
            resume = _line_end_hyphen(value, i - 1)
            if resume is not None:
                if hyphens == "keep":
                    out.append(ch)
                    index.append(i - 1)
                i = resume
                continue
        if ch.isspace():
            if out and out[-1] != " ":
                out.append(" ")
                index.append(i - 1)
            continue
        if ch == "।" and out and out[-1] == " ":  # "শব্দ ।" == "শব্দ।"
            out.pop()
            index.pop()
        out.append(ch)
        index.append(i - 1)
    while out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def _span(text: str, index: list[int], start: int, end: int) -> tuple[int, int]:
    """Source span [s, e) for normalized [start, end), trimmed of surrounding whitespace."""
    s, e = index[start], index[end - 1] + 1
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return s, e


_WORDS = re.compile(r"\S+")


def _fuzzy(norm_text: str, norm_quote: str, lo: int, hi: int) -> tuple[float, int, int] | None:
    """Best word-aligned window of norm_text[lo:hi] with char ratio >= FUZZY_MIN_RATIO.

    One word-level alignment (difflib on word lists) finds where the quote sits; the
    character ratio is then computed only for a few windows around that place, whose
    edges are word boundaries. Linear in practice, so long quotes stay fast.
    """
    words = [(m.start(), m.end()) for m in _WORDS.finditer(norm_text, lo, hi)]
    quote_words = norm_quote.split(" ")
    if not words:
        return None
    tokens = [norm_text[a:b] for a, b in words]
    blocks = [b for b in SequenceMatcher(None, tokens, quote_words, autojunk=False).get_matching_blocks() if b.size]
    if not blocks:
        return None
    # Keep the blocks that agree on where the quote starts (stray matches elsewhere are ignored).
    offsets = sorted(b.a - b.b for b in blocks for _ in range(b.size))
    center, slack = offsets[len(offsets) // 2], max(2, len(quote_words) // 5)
    kept = [b for b in blocks if abs((b.a - b.b) - center) <= slack]
    first, last = kept[0], kept[-1]
    ws = first.a - first.b
    we = last.a + last.size + (len(quote_words) - last.b - last.size)
    best: tuple[float, int, int] | None = None
    for a in {max(0, ws + d) for d in (-1, 0, 1)}:
        for b in {min(len(words), we + d) for d in (-1, 0, 1)}:
            if b <= a:
                continue
            s, e = words[a][0], words[b - 1][1]
            matcher = SequenceMatcher(None, norm_text[s:e], norm_quote, autojunk=False)
            if matcher.real_quick_ratio() < FUZZY_MIN_RATIO or matcher.quick_ratio() < FUZZY_MIN_RATIO:
                continue
            ratio = matcher.ratio()
            if ratio >= FUZZY_MIN_RATIO and (best is None or ratio > best[0]):
                best = (ratio, s, e)
    return best


def locate_normalized(quote: str, text: str) -> Located | None:
    """Steps 1-2 only (exact, then normalized with each line-end hyphen mode); never fuzzy."""
    needle = unicodedata.normalize("NFC", quote).strip()
    if not needle or not text:
        return None
    at = text.find(needle)
    if at >= 0:
        return Located(needle, at, at + len(needle), "exact")
    for mode in HYPHEN_MODES:
        norm_text, index = _normalize(text, mode)
        norm_quote, _ = _normalize(needle, mode)
        at = norm_text.find(norm_quote) if norm_quote else -1
        if at >= 0:
            s, e = _span(text, index, at, at + len(norm_quote))
            return Located(text[s:e], s, e, "normalized")
    return None


def locate_quote(quote: str | None, chunk_text: str,
                 hint: tuple[int, int] | None = None) -> Located | None:
    """The exact span of `chunk_text` that `quote` stands for, or None (not in the source)."""
    if not quote or not quote.strip() or not chunk_text:
        return None
    text = unicodedata.normalize("NFC", chunk_text)
    if text != chunk_text:
        return None  # stored chunks are NFC; refuse to map offsets on anything else
    needle = unicodedata.normalize("NFC", quote).strip()
    at = text.find(needle)
    if at >= 0:
        return Located(needle, at, at + len(needle), "exact")

    found = locate_normalized(needle, text)
    if found is not None:
        return found
    norm_text, index = _normalize(text)
    norm_quote, _ = _normalize(needle)
    if not norm_quote or not norm_text:
        return None

    if len(norm_quote) < FUZZY_MIN_CHARS or len(norm_quote.split()) < FUZZY_MIN_WORDS:
        return None
    regions = [(0, len(norm_text))]
    if hint is not None:  # look near the referenced sentences first, then everywhere
        lo = next((k for k, src in enumerate(index) if src >= hint[0]), 0)
        hi = next((k for k, src in enumerate(index) if src >= hint[1]), len(norm_text))
        regions.insert(0, (max(0, lo - 40), min(len(norm_text), hi + 40)))
    for lo, hi in regions:
        best = _fuzzy(norm_text, norm_quote, lo, hi)
        if best is not None:
            ratio, ns, ne = best
            s, e = _span(text, index, ns, ne)
            return Located(text[s:e], s, e, "fuzzy", round(ratio, 3))
    return None


def segments(chunk_text: str) -> list[tuple[int, int]]:
    """Sentence/line spans [start, end) of the chunk, numbered 1.. in the prompt."""
    spans, start = [], 0
    for match in _SEGMENT_END.finditer(chunk_text):
        if chunk_text[start:match.start()].strip():
            spans.append((start, match.start()))
        start = match.end()
    if chunk_text[start:].strip():
        spans.append((start, len(chunk_text)))
    return spans


def segment_hint(chunk_text: str, numbers: list[int] | None) -> tuple[int, int] | None:
    """Character span covered by the referenced sentence numbers (1-based), if valid."""
    spans = segments(chunk_text)
    picked = [spans[n - 1] for n in (numbers or []) if isinstance(n, int) and 1 <= n <= len(spans)]
    return (min(s for s, _ in picked), max(e for _, e in picked)) if picked else None
