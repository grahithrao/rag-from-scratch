"""Embeddings: text -> dense vectors, computed locally.

A Sentence-Transformers model runs on the host so indexing and querying cost
nothing and work offline once the model is cached. Loading takes a few seconds,
so the model is created once and reused for the life of the process.
"""

from __future__ import annotations

import logging
import threading

from langchain_core.embeddings import Embeddings

from app.config import settings
from app.rag.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

_embeddings: Embeddings | None = None
_lock = threading.Lock()


def _build_embeddings(model_name: str, device: str) -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings

    logger.info("Loading embedding model '%s' on %s…", model_name, device)
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        # Unit-normalised vectors make cosine distance well behaved in [0, 2].
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": settings.embedding_batch_size,
        },
    )


def get_embeddings(
    model_name: str | None = None, device: str | None = None
) -> Embeddings:
    """Return the shared embedding model, loading it on first use.

    Raises:
        EmbeddingError: if the model cannot be downloaded or loaded.
    """
    global _embeddings

    name = model_name or settings.embedding_model
    dev = device or settings.embedding_device

    if _embeddings is not None and model_name is None and device is None:
        return _embeddings

    with _lock:
        if _embeddings is not None and model_name is None and device is None:
            return _embeddings
        try:
            instance = _build_embeddings(name, dev)
            # Force the lazy weight load now so failures surface here, not
            # halfway through indexing a user's document.
            instance.embed_query("warmup")
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(
                f"Could not load embedding model '{name}'. Check the model name and "
                f"your network connection for the first download ({exc})."
            ) from exc
        if model_name is None and device is None:
            _embeddings = instance
        return instance


def embedding_dimension() -> int:
    """Vector width of the active embedding model."""
    return len(get_embeddings().embed_query("dimension probe"))


def is_ready() -> bool:
    """True when the embedding model is loaded and usable."""
    try:
        get_embeddings()
    except EmbeddingError:
        return False
    return True


def reset_embeddings() -> None:
    """Drop the cached model. Used by tests and by config reloads."""
    global _embeddings
    with _lock:
        _embeddings = None
