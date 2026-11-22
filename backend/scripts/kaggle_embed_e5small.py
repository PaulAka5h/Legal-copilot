"""Standalone e5-small ONNX int8 embedding for a Kaggle notebook (no project imports).

Input:  JSONL from `python -m app.rag.embed export`
        {chunk_id, text, content_hash, model, embedding_version, model_sha256}
        and the model bundle (model.onnx + tokenizer.json from scripts/export_e5_small_onnx.py,
        uploaded as a Kaggle dataset, or rebuilt there with that script).
Output: parquet {chunk_id, content_hash, embedding (384 float32, unit norm), model,
        embedding_version, model_sha256} for `python -m app.rag.embed import`, which
        checks content_hash, model, version, model_sha256, dims and norm again.

Kaggle usage (internet on only if you rebuild the model there):
    !pip -q install onnxruntime==1.32.0 tokenizers pyarrow numpy
    !python kaggle_embed_e5small.py --input /kaggle/input/<dataset>/chunks.jsonl \
        --model-dir /kaggle/input/<model-dataset> --output /kaggle/working/embeddings.parquet

Runs on onnxruntime's CPU provider in one process per core. A GPU does not help: the
int8 dynamic-quantization kernels are CPU kernels, and running the fp32 model on a GPU
would give different vectors from the int8 query embedder on the server (search would
then compare two different recipes). Every text is encoded alone (no batching or
padding), exactly like app.rag.search.e5_small_onnx, so the vectors are identical to
the local worker's. Only public legal knowledge-base text should ever be passed here.
"""

import argparse
import hashlib
import json
import multiprocessing
import os
import sys
import time
import unicodedata

MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_VERSION = 1
MODEL_SHA256 = "f5c0888fe75d7bd39d468b23417c8831247b70078ecc19e72041df3d86676842"
DIMENSION = 384
MAX_TOKENS = 512
PASSAGE_PREFIX = "passage: "

_session = _tokenizer = None


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _init(model_dir: str) -> None:
    global _session, _tokenizer
    import onnxruntime as ort
    from tokenizers import Tokenizer

    _tokenizer = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
    _tokenizer.no_padding()
    _tokenizer.enable_truncation(max_length=MAX_TOKENS)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    # Same level as the app (EXTENDED: bit-identical vectors, ~290 MB less RAM than ALL).
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
    options.log_severity_level = 3
    _session = ort.InferenceSession(os.path.join(model_dir, "model.onnx"), options,
                                    providers=["CPUExecutionProvider"])


def _embed(text: str):
    import numpy as np

    ids = np.array([_tokenizer.encode(PASSAGE_PREFIX + unicodedata.normalize("NFC", text)).ids], dtype=np.int64)
    mask = np.ones_like(ids)
    feeds = {"input_ids": ids, "attention_mask": mask}
    if any(i.name == "token_type_ids" for i in _session.get_inputs()):
        feeds["token_type_ids"] = np.zeros_like(ids)
    hidden = _session.run(["last_hidden_state"], feeds)[0].astype(np.float32)
    pooled = hidden.mean(axis=1)[0]  # one unpadded text: every token counts
    return (pooled / np.linalg.norm(pooled)).astype(np.float32)


def load_rows(path: str) -> list[dict]:
    rows, seen = [], set()
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if (row.get("model"), row.get("embedding_version"), row.get("model_sha256")) != (
                    MODEL, EMBEDDING_VERSION, MODEL_SHA256):
                sys.exit(f"line {line_no}: exported for another model, version or ONNX build")
            if row["chunk_id"] in seen:
                sys.exit(f"line {line_no}: duplicate chunk_id")
            seen.add(row["chunk_id"])
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--model-dir", required=True, help="Directory with model.onnx and tokenizer.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--processes", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()

    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    if sha256_file(os.path.join(args.model_dir, "model.onnx")) != MODEL_SHA256:
        sys.exit("model.onnx is not the pinned e5-small int8 build; rebuild it with export_e5_small_onnx.py")
    rows = load_rows(args.input)
    if not rows:
        sys.exit("No rows in input")

    started = time.perf_counter()
    with multiprocessing.Pool(args.processes, initializer=_init, initargs=(args.model_dir,)) as pool:
        vectors = np.stack(pool.map(_embed, [r["text"] for r in rows], chunksize=16))
    seconds = time.perf_counter() - started

    norms = np.linalg.norm(vectors, axis=1)
    if vectors.shape != (len(rows), DIMENSION) or not np.all(np.isfinite(vectors)) or np.any(
            np.abs(norms - 1) > 1e-3):
        sys.exit("Model returned invalid vectors")

    table = pa.table({
        "chunk_id": [r["chunk_id"] for r in rows],
        "content_hash": [r["content_hash"] for r in rows],
        "embedding": pa.FixedSizeListArray.from_arrays(pa.array(vectors.ravel(), type=pa.float32()), DIMENSION),
        "model": [MODEL] * len(rows),
        "embedding_version": pa.array([EMBEDDING_VERSION] * len(rows), type=pa.int32()),
        "model_sha256": [MODEL_SHA256] * len(rows),
    })
    pq.write_table(table, args.output)
    print(json.dumps({
        "rows": len(rows), "processes": args.processes, "encode_seconds": round(seconds, 2),
        "seconds_per_100_chunks": round(100 * seconds / len(rows), 2), "output": args.output,
    }, indent=2))


if __name__ == "__main__":
    main()
