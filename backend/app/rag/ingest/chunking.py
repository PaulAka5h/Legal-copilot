"""Section -> chunk splitting measured with the embedding model's tokenizer.

Every chunk is `header + body slice`, where the body slice is an exact
substring of the section text (word boundaries, no re-encoding), so quotes can
later be checked against stored text. Token counts include the "passage: "
prefix and special tokens, which is exactly what the embedder will encode.
"""

import re
from dataclasses import dataclass
from typing import Any, Protocol

EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_VERSION = 1
PASSAGE_PREFIX = "passage: "
MAX_TOKENS = 512
MAX_WORDS = 400
OVERLAP = 0.15
_WORD = re.compile(r"\S+")


class Tokenizer(Protocol):
    def __call__(self, text: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int


class TokenCounter:
    """Counts tokens the way the embedder sees them: prefix + text + special tokens."""

    def __init__(self, tokenizer: Tokenizer):
        self.tokenizer = tokenizer

    def count(self, text: str) -> int:
        return len(self.tokenizer(PASSAGE_PREFIX + text)["input_ids"])

    def word_token_ends(self, body: str, words: list[tuple[int, int]]) -> list[int]:
        """Cumulative body-token count at the end of each word (no prefix/specials)."""
        offsets = self.tokenizer(body, add_special_tokens=False, return_offsets_mapping=True)[
            "offset_mapping"
        ]
        ends, t = [], 0
        for _, word_end in words:
            while t < len(offsets) and offsets[t][0] < word_end:
                t += 1
            ends.append(t)
        return ends


def load_counter(model_name: str = EMBEDDING_MODEL) -> TokenCounter:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    # We only measure here; MAX_TOKENS is enforced by chunk_section. This silences
    # the "longer than maximum sequence length" warning for whole-section counts.
    tokenizer.model_max_length = 10**9
    return TokenCounter(tokenizer)


def section_header(act_title: str, year: str | None, number: str | None, heading: str | None) -> str:
    """`{act_title} ({year}) — Section {number}: {heading}` plus newline; absent parts omitted."""
    title = f"{act_title} ({year})" if year else act_title
    label = f"Section {number}" if number else "Section"
    return f"{title} — {label}: {heading}\n" if heading else f"{title} — {label}\n"


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
