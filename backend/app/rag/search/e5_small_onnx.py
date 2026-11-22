"""intfloat/multilingual-e5-small as ONNX int8 on this server (EMBEDDING_PROVIDER=e5_small_onnx).

Recipe (E5_SMALL_VERSION; change the number if any of it changes, so stored chunk
vectors and query vectors can never be mixed silently):
- model.onnx built by scripts/export_e5_small_onnx.py: the authors' fp32 ONNX export at a
  pinned revision, onnxruntime dynamic int8 quantization with UINT8 weights (exact on
  every x86-64 CPU). The file must have E5_SMALL_MODEL_SHA256;
- input: NFC text with "query: " (searches) or "passage: " (legal chunks), XLM-R
  tokenizer, truncated to 512 tokens including the special tokens;
- mean pooling over the attention mask, then L2 normalization; 384 dimensions.

Two tokenizer backends give the same XLM-R ids:
- `tokenizers` (tokenizer.json): the reference. Ingestion, the embed worker and the
  Kaggle script use it, so stored chunk vectors are reproducible exactly. Its Unigram
  trie costs ~285 MB of RAM.
- `sentencepiece` (sentencepiece.bpe.model, the model's original tokenizer): ~15 MB;
  used for queries on the 512 MB server. Checked on all 39,587 chunks and the 98 eval
  queries: identical ids except 8 chunks where two segmentations score the same (e.g.
  "contin|gen|cy" vs "cont|ingen|cy") and trailing whitespace, which queries strip.
Runs on CPU with onnxruntime only (no torch). Text never leaves the server and is
never logged.
"""

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from app.rag.text import nfc

E5_SMALL_MODEL = "intfloat/multilingual-e5-small"
E5_SMALL_VERSION = 1
E5_SMALL_DIM = 384
E5_SMALL_MAX_TOKENS = 512
E5_SMALL_MODEL_SHA256 = "f5c0888fe75d7bd39d468b23417c8831247b70078ecc19e72041df3d86676842"
E5_SMALL_SPM_SHA256 = "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865"
TOKENIZER_BACKENDS = ("tokenizers", "sentencepiece")
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "multilingual-e5-small-onnx-int8"


class ModelFilesError(RuntimeError):
    """The model bundle is missing or is not the pinned model."""


def model_dir() -> Path:
    return Path(os.getenv("E5_ONNX_DIR") or DEFAULT_MODEL_DIR)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_tokenizer(directory: Path | None = None):
    """The XLM-R tokenizer shipped with the model (same ids as e5-large's), no truncation."""
    from tokenizers import Tokenizer

    path = (directory or model_dir()) / "tokenizer.json"
    if not path.is_file():
        raise ModelFilesError(f"{path} not found; run scripts/export_e5_small_onnx.py")
    tokenizer = Tokenizer.from_file(str(path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer


class _Ids:
    __slots__ = ("ids",)

    def __init__(self, ids: list[int]) -> None:
        self.ids = ids


class XlmrSentencePiece:
    """XLM-R ids from sentencepiece.bpe.model, as the fairseq/transformers XLM-R tokenizer
    maps them: <s>=0, <pad>=1, </s>=2, <unk>=3, every other piece = sentencepiece id + 1.
    encode() adds <s> ... </s> and truncates to max_length like tokenizers does."""

    def __init__(self, path: Path, verify: bool = True) -> None:
        import sentencepiece

        if not path.is_file():
            raise ModelFilesError(f"{path} not found; run scripts/export_e5_small_onnx.py")
        if verify and sha256_file(path) != E5_SMALL_SPM_SHA256:
            raise ModelFilesError("sentencepiece.bpe.model is not the pinned file (SHA-256 differs)")
        self._sp = sentencepiece.SentencePieceProcessor(model_file=str(path))
        self.max_length: int | None = None

    def enable_truncation(self, max_length: int) -> None:
        self.max_length = max_length

    def encode(self, text: str) -> _Ids:
        pieces = [3 if i == 0 else i + 1 for i in self._sp.encode(text)]  # sentencepiece <unk> is 0
        if self.max_length is not None:
            pieces = pieces[: self.max_length - 2]
        return _Ids([0, *pieces, 2])


def mean_pool_normalize(hidden: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """[batch, tokens, dim] + [batch, tokens] -> unit-length [batch, dim] float32."""
    weights = mask[..., None].astype(np.float32)
    pooled = (hidden.astype(np.float32) * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    if not np.all(np.isfinite(pooled)) or np.any(norms == 0):
        raise ValueError("e5-small produced a zero or non-finite vector")
    return (pooled / norms).astype(np.float32)


class E5SmallOnnx:
    """One onnxruntime session. `threads` = intra-op threads (1 on a small server; more for bulk)."""

    model_name = E5_SMALL_MODEL
    embedding_version = E5_SMALL_VERSION
    dimension = E5_SMALL_DIM

    def __init__(self, directory: Path | None = None, threads: int = 1, verify: bool = True,
                 tokenizer: str = "tokenizers") -> None:
        import onnxruntime as ort

        if tokenizer not in TOKENIZER_BACKENDS:
            raise ValueError(f"tokenizer must be one of {TOKENIZER_BACKENDS}")

        directory = directory or model_dir()
        model_path = directory / "model.onnx"
        if not model_path.is_file():
            raise ModelFilesError(f"{model_path} not found; run scripts/export_e5_small_onnx.py")
        if verify and sha256_file(model_path) != E5_SMALL_MODEL_SHA256:
            raise ModelFilesError("model.onnx is not the pinned e5-small int8 build (SHA-256 differs)")
        if tokenizer == "sentencepiece":
            self.tokenizer = XlmrSentencePiece(directory / "sentencepiece.bpe.model", verify)
        else:
            self.tokenizer = load_tokenizer(directory)
        self.tokenizer.enable_truncation(max_length=E5_SMALL_MAX_TOKENS)  # counts <s> and </s>

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        # Small, steady memory on a 512 MB server: no arena that keeps the longest input's
        # buffers, no memory-pattern pre-allocation.
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        # EXTENDED, not the default ALL: ALL adds layout transforms that pre-pack the weights
        # and raise RSS from ~185 MB to ~475 MB (peak ~550 MB during load: OOM in 512 MB).
        # The vectors are bit-identical to ALL (checked), so stored embeddings stay valid.
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
        options.log_severity_level = 3
        self.session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: Sequence[str], prefix: str) -> np.ndarray:
        """One text per run, never batched: dynamic int8 quantization scales activations
        over the whole input tensor, so batch neighbours and padding would change a
        text's vector. Alone, a text gives the same vector on any machine, thread count
        or call site (measured: 0.0 difference; and faster than padded batches)."""
        out = np.empty((len(texts), E5_SMALL_DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            encoding = self.tokenizer.encode(prefix + nfc(text))
            ids = np.array([encoding.ids], dtype=np.int64)
            mask = np.ones_like(ids)
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feeds["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(["last_hidden_state"], feeds)[0]
            out[row] = mean_pool_normalize(hidden, mask)[0]
        return out


class E5SmallQueryEmbedder:
    """Search side: one "query: " vector."""

    model_name = E5_SMALL_MODEL
    embedding_version = E5_SMALL_VERSION

    def __init__(self, model: E5SmallOnnx) -> None:
        self.model = model

    def embed_query(self, query: str) -> list[float]:
        # Strip: a trailing space would add a lone "▁" token under `tokenizers` only.
        return self.model.encode([query.strip()], QUERY_PREFIX)[0].tolist()


class E5SmallDocumentEmbedder:
    """Knowledge-base side (python -m app.rag.embed): "passage: " vectors."""

    model_name = E5_SMALL_MODEL
    embedding_version = E5_SMALL_VERSION
    device = "cpu-onnx-int8"

    def __init__(self, model: E5SmallOnnx) -> None:
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, PASSAGE_PREFIX).tolist()
