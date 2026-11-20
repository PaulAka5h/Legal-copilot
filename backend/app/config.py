from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="Legal Copilot API", min_length=1)
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

    # Malware scanning: "none" means not configured (dev processes with a warning;
    # production refuses uploads).
    malware_scanner: Literal["none"] = "none"
    ocr_languages: str = "ben+eng"
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

    # Analysis abstains below these relevance thresholds (calibrated 2026-11-20 on the
    # 20-Act set: relevant queries' best cosine >= 0.80, unrelated <= 0.78).
    analysis_min_similarity: float = Field(default=0.79, ge=0, le=1)
    analysis_min_rerank_score: float = Field(default=0.1, ge=0, le=1)

    @property
    def secure_session_cookie(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.app_env == "production"
