from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    openai_api_key: str = ""
    pinecone_api_key: str = ""
    pinecone_index_name: str = "secure-rag"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    openai_chat_model: str = "gpt-5.6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    jwt_secret: str = "replace-me"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_audience: str = "secure-rag-api"
    jwt_issuer: str = "secure-rag-api"
    require_auth: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_storage_uri: str = "memory://"
    retrieval_top_k: int = 8
    rerank_top_k: int = 5
    min_retrieval_score: float = 0.20
    max_query_chars: int = 2000
    max_doc_chars: int = 2_000_000
    max_upload_bytes: int = 25_000_000  # 25 MB
    max_chunk_chars: int = 5000
    embedding_batch_size: int = 64
    max_context_chars: int = 24_000
    max_answer_chars: int = 12_000
    provider_max_attempts: int = 2
    provider_concurrency_limit: int = 8
    provider_operation_timeout_seconds: int = 90
    ingestion_stale_after_minutes: int = 30
    ingestion_lease_seconds: int = 600
    ingestion_max_attempts: int = 3
    ingestion_retry_backoff_seconds: int = 5
    max_pdf_pages: int = 200
    max_archive_entries: int = 500
    max_archive_uncompressed_bytes: int = 50_000_000
    allow_local_dev_tokens: bool = False
    cors_allowed_origins: str = ""
    database_url: str = "postgresql+asyncpg://secure_rag:CHANGE_ME@localhost:5432/secure_rag"
    pinecone_deletion_protection: Literal["enabled", "disabled"] = "enabled"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    log_level: str = "INFO"

    @property
    def jwt_secret_configured(self) -> bool:
        return self.jwt_secret != "replace-me" and len(self.jwt_secret) >= 32

    @model_validator(mode="after")
    def validate_runtime_limits(self) -> "Settings":
        if self.max_upload_bytes < 1 or self.max_upload_bytes > 50_000_000:
            raise ValueError("MAX_UPLOAD_BYTES must be between 1 and 50,000,000")
        if self.max_doc_chars < 1 or self.max_doc_chars > self.max_upload_bytes:
            raise ValueError("MAX_DOC_CHARS must be positive and no larger than MAX_UPLOAD_BYTES")
        if not 1 <= self.max_chunk_chars <= self.max_doc_chars:
            raise ValueError("MAX_CHUNK_CHARS must be within the document size limit")
        if not 1 <= self.embedding_batch_size <= 2048:
            raise ValueError("EMBEDDING_BATCH_SIZE must be between 1 and 2048")
        if not 1 <= self.max_context_chars <= 200_000:
            raise ValueError("MAX_CONTEXT_CHARS must be between 1 and 200,000")
        if not 1 <= self.max_answer_chars <= 100_000:
            raise ValueError("MAX_ANSWER_CHARS must be between 1 and 100,000")
        if not 1 <= self.provider_max_attempts <= 3:
            raise ValueError("PROVIDER_MAX_ATTEMPTS must be between 1 and 3")
        if not 1 <= self.provider_concurrency_limit <= 64:
            raise ValueError("PROVIDER_CONCURRENCY_LIMIT must be between 1 and 64")
        if not 1 <= self.provider_operation_timeout_seconds <= 600:
            raise ValueError("PROVIDER_OPERATION_TIMEOUT_SECONDS must be between 1 and 600")
        if not 60 <= self.ingestion_lease_seconds <= 3_600:
            raise ValueError("INGESTION_LEASE_SECONDS must be between 60 and 3,600")
        if not 5 <= self.ingestion_stale_after_minutes <= 1_440:
            raise ValueError("INGESTION_STALE_AFTER_MINUTES must be between 5 and 1,440")
        if not 1 <= self.ingestion_max_attempts <= 10:
            raise ValueError("INGESTION_MAX_ATTEMPTS must be between 1 and 10")
        if not 1 <= self.ingestion_retry_backoff_seconds <= 300:
            raise ValueError("INGESTION_RETRY_BACKOFF_SECONDS must be between 1 and 300")
        if not 1 <= self.max_pdf_pages <= 10_000:
            raise ValueError("MAX_PDF_PAGES must be between 1 and 10,000")
        if not 1 <= self.max_archive_entries <= 10_000:
            raise ValueError("MAX_ARCHIVE_ENTRIES must be between 1 and 10,000")
        if not 1 <= self.max_archive_uncompressed_bytes <= 500_000_000:
            raise ValueError("MAX_ARCHIVE_UNCOMPRESSED_BYTES is invalid")
        if (
            not 1 <= self.retrieval_top_k <= 100
            or not 1 <= self.rerank_top_k <= self.retrieval_top_k
        ):
            raise ValueError("Retrieval limits are invalid")
        if not 0 <= self.min_retrieval_score <= 1:
            raise ValueError("MIN_RETRIEVAL_SCORE must be between 0 and 1")
        if self.rate_limit_per_minute < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be positive")
        if not self.rate_limit_storage_uri:
            raise ValueError("RATE_LIMIT_STORAGE_URI must not be empty")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        if not 5 <= self.access_token_minutes <= 60:
            raise ValueError("ACCESS_TOKEN_MINUTES must be between 5 and 60")
        if not 1 <= self.refresh_token_days <= 90:
            raise ValueError("REFRESH_TOKEN_DAYS must be between 1 and 90")
        origins = [
            origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()
        ]
        if any(
            origin == "*" or not origin.startswith(("http://", "https://")) for origin in origins
        ):
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must be a comma-separated HTTP(S) origin allowlist"
            )
        if self.environment == "production":
            if not self.require_auth:
                raise ValueError("REQUIRE_AUTH must be true in production")
            if self.allow_local_dev_tokens:
                raise ValueError("ALLOW_LOCAL_DEV_TOKENS must be false in production")
            if not self.jwt_secret_configured:
                raise ValueError(
                    "JWT_SECRET must be a non-default secret of at least 32 characters"
                )
            if "CHANGE_ME" in self.database_url:
                raise ValueError("DATABASE_URL must use a real production credential")
            if self.pinecone_deletion_protection != "enabled":
                raise ValueError("PINECONE_DELETION_PROTECTION must be enabled in production")
            if self.rate_limit_storage_uri.startswith("memory://"):
                raise ValueError("A shared rate-limit store is required in production")
        elif self.environment != "development" and self.allow_local_dev_tokens:
            raise ValueError("ALLOW_LOCAL_DEV_TOKENS is only permitted in development")
        return self


settings = Settings()
