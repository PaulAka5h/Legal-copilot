"""Sentence spans for page text (mock extractor, OCR text).

A sentence ends at ".", "!", "?" or the danda "।" followed by whitespace and a
sentence start (capital, digit, bracket, quote, or a Bangla letter), never:
- after an abbreviation: No., Mr., Ltd., Dr., v., s., Tk., নং., ... or a single
  capital initial (M. A. Karim);
- inside a number: "5,00,000" and "5.5" have no whitespace after the mark.

A single line break is layout, not a boundary (PDF and OCR text wraps lines);
it ends a sentence only after a heading line ("3. Timeline") or a blank line.
Spans index the original text, so text[start:end] is a verbatim quote.
"""

import re

ABBREVIATIONS = frozenset({
    "no", "nos", "mr", "mrs", "ms", "dr", "ltd", "co", "inc", "corp", "pvt", "v", "vs", "s", "ss", "sec",
    "art", "ch", "cl", "para", "st", "jr", "sr", "prof", "hon", "adv", "govt", "dept", "rs", "tk", "etc",
    "e.g", "i.e", "viz", "approx", "ref", "vol", "pp", "p", "j", "mst", "md",
    "নং", "ডা", "মো", "মোছা", "মোসাঃ", "মোঃ",
})

_TERMINATOR = re.compile(r"[.!?।]+(?=\s|$)")
_SENTENCE_START = re.compile(r"[\"'“‘(\[A-Z0-9০-৯ঀ-৿]")
_WORD_BEFORE = re.compile(r"([\w.ঀ-৿]+)$")
_HEADING = re.compile(r"^\s*(?:\d+|[০-৯]+)[.)]\s+[^\n.!?।]{1,60}$")


def _is_abbreviation(text: str, mark_at: int) -> bool:
    if text[mark_at] != ".":
        return False
    found = _WORD_BEFORE.search(text, 0, mark_at)
    if not found:
        return False
    word = found.group(1).strip(".")
    if len(word) == 1 and word.isalpha() and word.isupper():  # initials: M. A. Karim
        return True
    return word.lower() in ABBREVIATIONS


def _is_list_marker(text: str, mark_at: int) -> bool:
    """'3.' or '(b)' style numbering at the start of a line is not a sentence end."""
    line_start = text.rfind("\n", 0, mark_at) + 1
    return bool(re.fullmatch(r"\s*(?:\d+|[০-৯]+)", text[line_start:mark_at]))


def _hard_breaks(text: str) -> list[int]:
    """Offsets of line breaks that end a sentence: blank lines and the end of heading lines."""
    breaks = [m.start() for m in re.finditer(r"\n\s*\n", text)]
    offset = 0
    for line in text.split("\n"):
        end = offset + len(line)
        if _HEADING.match(line):
            breaks.append(end)
        offset = end + 1
    return sorted(set(breaks))


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """[start, end) spans of the sentences in text, trimmed of surrounding whitespace."""
    cuts: list[int] = []
    for match in _TERMINATOR.finditer(text):
        end = match.end()
        rest = text[end:].lstrip()
        if not rest:
            cuts.append(end)
            continue
        if _is_abbreviation(text, match.start()) or _is_list_marker(text, match.start()):
            continue
        if _SENTENCE_START.match(rest):
            cuts.append(end)
    cuts = sorted(set(cuts + _hard_breaks(text) + [len(text)]))
    spans: list[tuple[int, int]] = []
    start = 0
    for cut in cuts:
        s, e = start, cut
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            spans.append((s, e))
        start = cut
    return spans
