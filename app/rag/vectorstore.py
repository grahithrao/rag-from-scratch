"""ChromaDB persistence layer.

Wraps ``langchain_chroma.Chroma`` with the operations the app actually needs:
add chunks, similarity search with scores, delete by document, and counting.
Storage is a persistent local directory, so restarting the API keeps every
previously indexed document.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from langchain_core.documents import Document

from app.config import settings
from app.rag.chunker import Chunk
from app.rag.exceptions import VectorStoreError

logger = logging.getLogger(__name__)

_store: Any | None = None
_lock = threading.RLock()


def get_store() -> Any:
    """Return the shared persistent Chroma collection.

    Raises:
        VectorStoreError: if the store cannot be opened.
    """
    global _store
    if _store is not None:
        return _store

    with _lock:
        if _store is not None:
            return _store
        from langchain_chroma import Chroma

        from app.rag.embeddings import get_embeddings

        settings.ensure_directories()
        try:
            _store = Chroma(
                collection_name=settings.chroma_collection,
                embedding_function=get_embeddings(),
                persist_directory=str(settings.chroma_dir),
                # Cosine keeps distances in [0, 2] for normalised vectors, which
                # gives us a stable threshold and a clean 0-1 relevance score.
                collection_metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(
                f"Could not open the vector database at '{settings.chroma_dir}': {exc}"
            ) from exc
        return _store


def add_chunks(chunks: list[Chunk]) -> int:
    """Embed and persist ``chunks``. Returns how many were written."""
    if not chunks:
        return 0
    store = get_store()
    documents = [
        Document(page_content=chunk.text, metadata=chunk.to_metadata())
        for chunk in chunks
    ]
    ids = [chunk.id for chunk in chunks]
    try:
        # Batch to stay well under Chroma's per-call ceiling on large documents.
        batch = 256
        for start in range(0, len(documents), batch):
            store.add_documents(
                documents=documents[start : start + batch],
                ids=ids[start : start + batch],
            )
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreError(f"Failed to store embeddings: {exc}") from exc
    return len(documents)


def similarity_search(
    query: str, k: int, document_ids: list[str] | None = None
) -> list[tuple[Document, float]]:
    """Return the ``k`` nearest chunks as ``(document, distance)`` pairs.

    Lower distance means a closer match.
    """
    store = get_store()
    where: dict[str, Any] | None = None
    if document_ids:
        where = (
            {"document_id": document_ids[0]}
            if len(document_ids) == 1
            else {"document_id": {"$in": document_ids}}
        )
    try:
        return store.similarity_search_with_score(query, k=k, filter=where)
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreError(f"Similarity search failed: {exc}") from exc


def delete_document(document_id: str) -> int:
    """Remove every vector belonging to ``document_id``. Returns the count."""
    store = get_store()
    try:
        existing = store.get(where={"document_id": document_id}, include=[])
        ids = existing.get("ids", []) if existing else []
        if ids:
            store.delete(ids=ids)
        return len(ids)
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreError(f"Failed to delete document vectors: {exc}") from exc


def clear_all() -> int:
    """Drop every vector in the collection. Returns how many were removed."""
    global _store
    store = get_store()
    try:
        existing = store.get(include=[])
        ids = existing.get("ids", []) if existing else []
        if ids:
            store.delete(ids=ids)
        return len(ids)
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreError(f"Failed to clear the vector store: {exc}") from exc


def count_chunks(document_id: str | None = None) -> int:
    """Number of stored vectors, optionally for a single document."""
    store = get_store()
    try:
        if document_id is None:
            return int(store._collection.count())  # noqa: SLF001 - no public API
        result = store.get(where={"document_id": document_id}, include=[])
        return len(result.get("ids", [])) if result else 0
    except Exception as exc:  # noqa: BLE001
        raise VectorStoreError(f"Failed to count stored chunks: {exc}") from exc


def has_document(document_id: str) -> bool:
    """True when at least one vector for ``document_id`` is stored."""
    return count_chunks(document_id) > 0


def is_ready() -> bool:
    """True when the collection can be opened and queried."""
    try:
        count_chunks()
    except VectorStoreError:
        return False
    return True


def reset_store() -> None:
    """Drop the cached handle so the next call reopens the collection."""
    global _store
    with _lock:
        _store = None
