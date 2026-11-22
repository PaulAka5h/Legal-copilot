"""Build the e5-small ONNX int8 model bundle (EMBEDDING_PROVIDER=e5_small_onnx).

    python scripts/export_e5_small_onnx.py [--out models/multilingual-e5-small-onnx-int8]

Standalone (no project imports): it runs in the Dockerfile.render build stage with only
numpy, onnx and onnxruntime installed, and locally with `uv run`.

1. Downloads intfloat/multilingual-e5-small at a pinned revision: onnx/model.onnx (the
   fp32 ONNX export the model authors published with optimum), onnx/tokenizer.json and
   sentencepiece.bpe.model. All are checked against pinned SHA-256 values.
2. Applies onnxruntime dynamic int8 quantization (quantize_dynamic) with UINT8 weights
   (U8U8). U8S8 can saturate on x86 CPUs without VNNI, which would make vectors depend
   on the CPU; U8U8 is exact on every x86-64 CPU, so the vectors made on a laptop, on a
   Kaggle box, and on Render are the same.
3. Writes model.onnx, tokenizer.json, sentencepiece.bpe.model and manifest.json (hashes, revision, recipe) and
   prints the manifest. Re-running with the same pinned inputs and library versions
   gives a byte-identical model; the Dockerfile checks the output hash.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
SOURCES = {
    "onnx/model.onnx": "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
    "onnx/tokenizer.json": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
    # The original XLM-R tokenizer: the server's low-memory query tokenizer.
    "sentencepiece.bpe.model": "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
}
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "models" / "multilingual-e5-small-onnx-int8"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(name: str, expected_sha: str, dest: Path) -> None:
    url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(tmp, "wb") as handle:
        shutil.copyfileobj(response, handle, 1 << 20)
    actual = sha256_file(tmp)
    if actual != expected_sha:
        tmp.unlink(missing_ok=True)
        sys.exit(f"{name}: SHA-256 {actual} does not match the pinned {expected_sha}")
    tmp.replace(dest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--expect-sha256", help="Fail unless the quantized model has this SHA-256")
    args = parser.parse_args()

    import onnx
    import onnxruntime
    from onnxruntime.quantization import QuantType, quantize_dynamic

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir:
        fp32 = Path(tmp_dir) / "model_fp32.onnx"
        download("onnx/model.onnx", SOURCES["onnx/model.onnx"], fp32)
        download("onnx/tokenizer.json", SOURCES["onnx/tokenizer.json"], args.out / "tokenizer.json")
        download("sentencepiece.bpe.model", SOURCES["sentencepiece.bpe.model"], args.out / "sentencepiece.bpe.model")
        int8 = Path(tmp_dir) / "model.onnx"
        quantize_dynamic(fp32, int8, weight_type=QuantType.QUInt8, per_channel=False, reduce_range=False)
        shutil.move(int8, args.out / "model.onnx")

    model_sha = sha256_file(args.out / "model.onnx")
    manifest = {
        "model": MODEL,
        "revision": REVISION,
        "source_sha256": SOURCES,
        "quantization": "onnxruntime.quantization.quantize_dynamic weight_type=QUInt8 per_channel=False "
                        "reduce_range=False",
        "onnx_version": onnx.__version__,
        "onnxruntime_version": onnxruntime.__version__,
        "model_sha256": model_sha,
        "tokenizer_sha256": sha256_file(args.out / "tokenizer.json"),
        "sentencepiece_sha256": sha256_file(args.out / "sentencepiece.bpe.model"),
        "model_bytes": os.path.getsize(args.out / "model.onnx"),
        "dimension": 384,
        "pooling": "mean over attention mask, then L2 normalize",
        "prefixes": {"query": "query: ", "passage": "passage: "},
        "max_tokens": 512,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if args.expect_sha256 and model_sha != args.expect_sha256:
        sys.exit(f"Quantized model SHA-256 {model_sha} is not the expected {args.expect_sha256}")


if __name__ == "__main__":
    main()
