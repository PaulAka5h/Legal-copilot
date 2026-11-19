"""Standalone embedding script for a Kaggle GPU notebook (no project imports).

Input:  JSONL from `python -m app.rag.embed export` with
        {chunk_id, text, content_hash, model, embedding_version}.
Output: parquet with chunk_id, content_hash, embedding (1024 float32, unit norm),
        model, embedding_version, for `python -m app.rag.embed import`.

Kaggle usage (GPU accelerator on; internet on to download the model once):
    !pip -q install sentence-transformers pyarrow
    !python kaggle_embed.py --input /kaggle/input/<dataset>/chunks.jsonl \
                            --output /kaggle/working/embeddings.parquet

The text is encoded as "passage: " + text. The model runs in fp16 on CUDA;
vectors are cast to float32 and L2-normalized in float32 so they are unit norm.
Only public legal knowledge-base text should ever be passed to this script.
"""

import argparse
import json
import sys
import time
import unicodedata

MODEL = "intfloat/multilingual-e5-large"
DIMENSION = 1024
PASSAGE_PREFIX = "passage: "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda",
                        help="cpu is for local testing only; fp16 is used only on cuda")
    return parser.parse_args()


def load_rows(path: str) -> list[dict]:
    rows, seen = [], set()
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("model") != MODEL:
                sys.exit(f"line {line_no}: model {row.get('model')!r} is not {MODEL}")
            if row["chunk_id"] in seen:
                sys.exit(f"line {line_no}: duplicate chunk_id")
            seen.add(row["chunk_id"])
            rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    import torch
    from sentence_transformers import SentenceTransformer

    if args.device == "cuda" and not torch.cuda.is_available():
        sys.exit("CUDA is not available; enable the GPU accelerator or pass --device cpu")
    rows = load_rows(args.input)
    if not rows:
        sys.exit("No rows in input")

    model = SentenceTransformer(MODEL, device=args.device)
    model.max_seq_length = 512
    if args.device == "cuda":
        model.half()

    texts = [PASSAGE_PREFIX + unicodedata.normalize("NFC", r["text"]) for r in rows]
    started = time.perf_counter()
    raw = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=False,
                       convert_to_numpy=True, show_progress_bar=True)
    seconds = time.perf_counter() - started

    vectors = raw.astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if vectors.shape[1] != DIMENSION or not np.all(np.isfinite(vectors)) or np.any(norms == 0):
        sys.exit("Model returned invalid vectors")
    vectors /= norms

    table = pa.table({
        "chunk_id": [r["chunk_id"] for r in rows],
        "content_hash": [r["content_hash"] for r in rows],
        "embedding": pa.FixedSizeListArray.from_arrays(pa.array(vectors.ravel(), type=pa.float32()), DIMENSION),
        "model": [MODEL] * len(rows),
        "embedding_version": pa.array([r["embedding_version"] for r in rows], type=pa.int32()),
    })
    pq.write_table(table, args.output)
    print(json.dumps({
        "rows": len(rows), "device": args.device, "fp16": args.device == "cuda",
        "batch_size": args.batch_size, "encode_seconds": round(seconds, 2),
        "seconds_per_100_chunks": round(100 * seconds / len(rows), 2), "output": args.output,
    }, indent=2))


if __name__ == "__main__":
    main()
