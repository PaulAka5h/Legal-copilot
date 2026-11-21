"""Check that EMBEDDING_PROVIDER=hf_api returns the same vectors as the local model.

    cd backend
    uv run python ../deploy/verify_hf_embeddings.py          # needs the `ml` group (torch)

Reads HF_API_TOKEN from the environment or backend/.env (never printed). Embeds 5
real queries from tests/rag/data/retrieval_queries_20_acts.json (3 English, 2
Bangla) with both providers and prints cosine similarities as a Markdown table.
The stored chunk embeddings were made by the local model, so hf_api is only safe
to use if every cosine is > 0.99. Exit code 0 only in that case.
"""

import math
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from app.rag.search.providers import (  # noqa: E402
    HF_FEATURE_EXTRACTION_URL,
    E5QueryEmbedder,
    HFApiQueryEmbedder,
)

THRESHOLD = 0.99
QUERIES = [
    "penalty for a police officer who neglects duty",
    "burden of proving the accused's case falls within an exception",
    "custody of children in suits for dissolution or nullity of marriage",
    "দায়িত্বে অবহেলার জন্য পুলিশ কর্মকর্তার শাস্তি",
    "বিবাহবিচ্ছেদ বা বিবাহ বাতিলের মামলায় সন্তানের হেফাজত",
]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main() -> int:
    token = os.environ.get("HF_API_TOKEN")
    if not token:
        print("Set HF_API_TOKEN (environment or backend/.env)", file=sys.stderr)
        return 2
    local, remote = E5QueryEmbedder(), HFApiQueryEmbedder(token)
    print(f"Endpoint: {HF_FEATURE_EXTRACTION_URL}\n")
    print("| # | Query | Language | Dims | Cosine (hf_api vs local) |")
    print("|---|---|---|---|---|")
    worst = 1.0
    for i, query in enumerate(QUERIES, start=1):
        a, b = local.embed_query(query), remote.embed_query(query)
        score = cosine(a, b)
        worst = min(worst, score)
        language = "bn" if any("ঀ" <= c <= "৿" for c in query) else "en"
        print(f"| {i} | {query} | {language} | {len(b)} | {score:.6f} |")
    verdict = "PASS" if worst > THRESHOLD else "FAIL"
    print(f"\nMinimum cosine {worst:.6f} -> {verdict} (threshold > {THRESHOLD})")
    return 0 if worst > THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
