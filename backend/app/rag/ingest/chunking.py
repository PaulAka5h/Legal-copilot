"""Section -> chunk splitting measured with the embedding model's tokenizer.

Every chunk is `header + body slice`, where the body slice is an exact
substring of the section text (word boundaries, no re-encoding), so quotes can
later be checked against stored text. Token counts include the "passage: "
prefix and special tokens, which is exactly what the embedder will encode.
The tokenizer is the one bundled with the e5-small ONNX model (XLM-R, the same token ids
as e5-large). It keeps a trailing-whitespace token that transformers drops, so a few
sections split one word differently from chunks made before 2026-11-22; both fit 512.
"""

import re
from dataclasses import dataclass
from typing import Any

from app.rag.search.e5_small_onnx import E5_SMALL_MAX_TOKENS, PASSAGE_PREFIX, load_tokenizer
from app.rag.text import nfc

# Label of the 1024-dim e5 providers (EMBEDDING_PROVIDER=local / hf_api). New chunks are
# labelled with the configured provider's model (pipeline.configured_embedding_label).
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_VERSION = 1
MAX_TOKENS = E5_SMALL_MAX_TOKENS  # 512 for e5-small and e5-large (same XLM-R tokenizer)
MAX_WORDS = 400
OVERLAP = 0.15
_WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int


class TokenCounter:
    """Counts tokens the way the embedder sees them: prefix + text + special tokens.

    `tokenizer` is a `tokenizers.Tokenizer` without truncation or padding.
    """

    def __init__(self, tokenizer: Any):
        self.tokenizer = tokenizer

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(PASSAGE_PREFIX + text).ids)

    def word_token_ends(self, body: str, words: list[tuple[int, int]]) -> list[int]:
        """Cumulative body-token count at the end of each word (no prefix/specials)."""
        offsets = self.tokenizer.encode(body, add_special_tokens=False).offsets
        ends, t = [], 0
        for _, word_end in words:
            while t < len(offsets) and offsets[t][0] < word_end:
                t += 1
            ends.append(t)
        return ends


def load_counter() -> TokenCounter:
    return TokenCounter(load_tokenizer())


_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_TRAILING = " \t.,;:)]"


_TRAILING_MARKER = re.compile(r"\s*\[[^\]]*\]\s*$")  # e.g. "Act, 1867 [Repealed]"


def title_ends_with_year(title: str, year: str) -> bool:
    """True if the title already ends with the year (Bangla or English digits), ignoring a trailing [marker]."""
    core = _TRAILING_MARKER.sub("", title).translate(_BN_DIGITS).rstrip(_TRAILING)
    return core.endswith(year.translate(_BN_DIGITS).strip())


def section_header(act_title: str, year: str | None, number: str | None, heading: str | None) -> str:
    """`{act_title} ({year}) — Section {number}: {heading}` plus newline, NFC.

    "(year)" is added only when the title does not already end with that year;
    absent parts are omitted.
    """
    title = act_title
    if year and year.strip() and not title_ends_with_year(act_title, year):
        title = f"{act_title} ({year})"
    label = f"Section {number}" if number else "Section"
    return nfc(f"{title} — {label}: {heading}\n" if heading else f"{title} — {label}\n")


def chunk_section(header: str, body: str, counter: TokenCounter) -> list[Chunk]:
    """Split body into header-prefixed chunks of at most MAX_TOKENS with ~15% word overlap."""
    whole = header + body
    whole_count = counter.count(whole)
    words = [m.span() for m in _WORD.finditer(body)]
    if whole_count <= MAX_TOKENS and len(words) <= MAX_WORDS:
        return [Chunk(0, whole, whole_count)]

    budget = MAX_TOKENS - counter.count(header)
    if budget <= 0:
        raise ValueError("Section header alone exceeds the token budget")
    ends = counter.word_token_ends(body, words)

    chunks: list[Chunk] = []
    start = 0
    while start < len(words):
        before = ends[start - 1] if start else 0
        end = start
        while (
            end + 1 < len(words)
            and end + 1 - start < MAX_WORDS
            and ends[end + 1] - before <= budget
        ):
            end += 1
        # Token counts are not exactly additive at slice edges; shrink until it fits.
        while True:
            text = header + body[words[start][0]:words[end][1]]
            count = counter.count(text)
            if count <= MAX_TOKENS:
                break
            if end == start:
                raise ValueError("A single word exceeds the token budget")
            end -= 1
        chunks.append(Chunk(len(chunks), text, count))
        if end == len(words) - 1:
            break
        overlap = max(1, int((end - start + 1) * OVERLAP))
        start = max(start + 1, end + 1 - overlap)
    return chunks
