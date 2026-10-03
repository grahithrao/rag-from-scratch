"""Centralised application configuration.

Every tunable knob of the RAG pipeline lives here and can be overridden with an
environment variable (or a ``.env`` file) so the same codebase can run locally,
in CI, or in a container without edits.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# Values that appear in .env.example; treated as "not configured".
_PLACEHOLDER_KEYS = {"your_api_key_here", "gsk_your_key_here", "changeme", "none"}


class Settings(BaseSettings):
    """Typed, validated settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ LLM
    groq_api_key: str = Field(default="", description="Groq API key.")
    groq_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Chat model served by Groq.",
    )
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1024, gt=0, le=32768)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    # ------------------------------------------------------------ Embeddings
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence-Transformers model used for local embeddings.",
    )
    embedding_device: str = Field(
        default="cpu", description="Torch device for the embedding model."
    )
    embedding_batch_size: int = Field(default=32, gt=0)

    # -------------------------------------------------------------- Chunking
    chunk_size: int = Field(default=1000, ge=100, le=8000)
    chunk_overlap: int = Field(default=150, ge=0, le=2000)

    # ------------------------------------------------------------- Retrieval
    top_k: int = Field(default=5, ge=1, le=50)
    # Chroma returns cosine *distance* in [0, 2]; anything above this is noise.
    max_distance: float = Field(default=1.15, ge=0.0, le=2.0)

    # ----------------------------------------------------------- Chat memory
    max_history_turns: int = Field(
        default=4, ge=0, le=20, description="User/assistant pairs kept for context."
    )

    # ------------------------------------------------------------- Storage
    upload_dir: Path = Field(default=BASE_DIR / "data" / "uploads")
    chroma_dir: Path = Field(default=BASE_DIR / "data" / "chroma")
    registry_path: Path = Field(default=BASE_DIR / "data" / "registry.json")
    chroma_collection: str = Field(default="rag_from_scratch")

    # ------------------------------------------------------------- Uploads
    max_upload_mb: float = Field(default=25.0, gt=0)

    # -------------------------------------------------------------- Server
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8001)
    api_base_url: str = Field(default="http://127.0.0.1:8001")
    cors_origins: str = Field(default="*")

    @field_validator("chunk_overlap")
    @classmethod
    def _overlap_must_be_smaller(cls, value: int, info) -> int:
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and value >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return value

    # ------------------------------------------------------------- Helpers
    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def has_groq_key(self) -> bool:
        """True only for a real key — the .env.example placeholder does not count."""
        key = self.groq_api_key.strip()
        return bool(key) and key not in _PLACEHOLDER_KEYS

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_directories(self) -> None:
        """Create the storage directories the app writes to."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings


settings = get_settings()
