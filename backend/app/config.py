from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Calibrated analysis thresholds per embedding provider (DOCS/eval_results.md).
# e5 (2026-11-20, 20-Act set): relevant queries' best cosine >= 0.80, unrelated <= 0.78.
# gemini-embedding-001 v1 (2026-11-21, 19-Act demo set, eval/retrieval.py): 33 relevant
# queries' best cosine >= 0.658, 12 off-topic <= 0.589; midpoint of the gap = 0.624.
# e5_small_onnx (2026-11-22, 19-Act set, rewrite + k=30/dense 1.5, eval/retrieval.py): relevant best
# cosine >= 0.83, off-topic <= 0.81, midpoint 0.82. PROVISIONAL: recalibrate on the full corpus.
DEFAULT_MIN_SIMILARITY = {"e5_small_onnx": 0.82, "local": 0.79, "hf_api": 0.79, "gemini": 0.624}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="PokkhoAI API", min_length=1)
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str | None = Field(default=None, min_length=1)
    app_origin: AnyHttpUrl = "http://localhost:3000"
    session_cookie_secure: bool | None = None
    session_idle_minutes: int = Field(default=30, gt=0)
    session_absolute_hours: int = Field(default=12, gt=0)
    mfa_encryption_key: str | None = None

    # Object storage (MinIO / S3). Keys are cases/{case_id}/documents/{document_id}.
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: SecretStr | None = None
    minio_bucket: str | None = None
    minio_secure: bool = False
    # Optional; set for S3-compatible hosts that need it (Backblaze B2: the region in
    # the endpoint, e.g. us-west-004). The endpoint is host[:port] only, no scheme/path.
    minio_region: str | None = None

    # Malware scanning: "none" means not configured (dev processes with a warning;
    # production refuses uploads).
    malware_scanner: Literal["none"] = "none"
    ocr_languages: str = "ben+eng"
    # Highest OCR render resolution; photos are scaled to an A4 page at this DPI.
    # 300 is Tesseract's sweet spot; Dockerfile.render uses 200 to fit 512 MB.
    ocr_dpi: int = Field(default=300, ge=100, le=600)
    # Documents extracted (rendered + OCR'd) at once per process; others wait their turn.
    # 1 keeps a 512 MB server safe: two scans at once measured 501 MiB with e5-small loaded.
    extraction_max_concurrent: int = Field(default=1, ge=1, le=16)
    max_pdf_pages: int = Field(default=200, gt=0)
    # Documents stuck in 'processing' longer than this are marked failed (retryable)
    # by a sweep at startup and by `python -m app.documents.recovery`.
    stuck_processing_minutes: int = Field(default=30, ge=5)
    sweep_stuck_documents_on_startup: bool = True

    # Fact extraction LLM. Only providers listed in DOCS/providers.md may be approved.
    llm_provider: Literal["mock", "ollama", "gemini"] = "mock"
    llm_approved_providers: str = "mock"
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=120, gt=0)
    # Gemini: free tier, SYNTHETIC SAMPLE DATA ONLY (DOCS/providers.md); refused in production.
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    # Second Gemini model, tried after GEMINI_MODEL keeps answering 429/503 (or fails);
    # e.g. gemini-2.5-flash. Unset = straight to the labelled mock.
    gemini_fallback_model: str | None = Field(default=None, min_length=1)

    # Embeddings. e5_small_onnx (default): intfloat/multilingual-e5-small, ONNX int8, on this
    # server (no API key; model bundle from scripts/export_e5_small_onnx.py, E5_ONNX_DIR).
    # local / hf_api: intfloat/multilingual-e5-large (on this server / on the
    # Hugging Face API). gemini: GEMINI_EMBEDDING_MODEL on the Gemini API (uses
    # GEMINI_API_KEY). hf_api and gemini send text off the server: synthetic demo data
    # only, refused in production (DOCS/providers.md). The legal knowledge base must be
    # embedded with the same model: search refuses a mismatch with 503.
    embedding_provider: Literal["e5_small_onnx", "local", "hf_api", "gemini"] = "e5_small_onnx"
    # onnxruntime intra-op threads for e5_small_onnx query embedding (1 on the 512 MB Render box).
    e5_onnx_threads: int = Field(default=1, ge=1, le=64)
    # Load the query embedder at startup (Render: its one-time load peak then never
    # coincides with an OCR upload, and the first search is fast). Off by default (tests).
    preload_query_embedder: bool = False
    hf_api_token: SecretStr | None = None
    hf_api_timeout_seconds: float = Field(default=30, gt=0)
    gemini_embedding_model: str = Field(default="gemini-embedding-001", min_length=1)
    gemini_embedding_timeout_seconds: float = Field(default=30, gt=0)

    # Legal search and analysis rewrite each new query once with the LLM (LLM_PROVIDER) into
    # Bangla + English + keywords and fuse the results (app.rag.search.query_rewrite). With
    # the mock LLM, or if the call fails, the query is searched as typed.
    search_query_rewrite: bool = True
    search_rewrite_timeout_seconds: float = Field(default=8, gt=0, le=60)
    # An analysis rewrites all its fact statements in ONE call (a JSON list): longer output.
    analysis_rewrite_timeout_seconds: float = Field(default=20, gt=0, le=60)
    # After a 429/503 or timeout, skip rewriting (plain query, no wait) for this long.
    search_rewrite_cooldown_seconds: float = Field(default=60, ge=0, le=3600)

    # Analysis abstains when no retrieved provision reaches this cosine similarity (mock
    # reranker). Unset = the calibrated default for the embedding model, because
    # cosine scales differ between models; see DEFAULT_MIN_SIMILARITY.
    analysis_min_similarity: float | None = Field(default=None, ge=0, le=1)
    analysis_min_rerank_score: float = Field(default=0.1, ge=0, le=1)

    @property
    def analysis_similarity_threshold(self) -> float:
        if self.analysis_min_similarity is not None:
            return self.analysis_min_similarity
        return DEFAULT_MIN_SIMILARITY[self.embedding_provider]

    @property
    def secure_session_cookie(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.app_env == "production"
