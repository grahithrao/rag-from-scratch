"""Document lifecycle: upload -> parse -> chunk -> embed -> index, plus deletion.

A small JSON registry on disk tracks what has been ingested, so the sidebar can
show filenames, page counts and chunk counts without scanning the vector store.
The registry is the bookkeeping; ChromaDB remains the source of truth for
vectors, and the two are reconciled on startup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.schemas import DocumentInfo, IndexStatus
from app.rag import vectorstore
from app.rag.chunker import chunk_document
from app.rag.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    InvalidFileError,
)
from app.rag.loader import detect_file_type, load_document

logger = logging.getLogger(__name__)

_registry_lock = threading.RLock()
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]")


# ------------------------------------------------------------------ utilities
def sanitize_filename(filename: str) -> str:
    """Reduce an uploaded name to a safe basename.

    Strips directory components (defeating ``../`` traversal), control
    characters and anything outside a conservative allowlist.
    """
    name = unicodedata.normalize("NFKC", filename or "")
    # Treat both separators as path separators regardless of host OS.
    name = name.replace("\\", "/").split("/")[-1]
    name = _UNSAFE_CHARS.sub("_", name).strip(" .")
    if not name:
        name = "document"
    if len(name) > 120:
        stem, dot, suffix = name.rpartition(".")
        name = f"{stem[:100]}{dot}{suffix[:15]}" if dot else name[:120]
    return name


def compute_document_id(content: bytes) -> str:
    """Content hash used as the document id — identical files share an id."""
    return hashlib.sha256(content).hexdigest()[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stored_path(document_id: str, filename: str) -> Path:
    return settings.upload_dir / f"{document_id}__{sanitize_filename(filename)}"


# ------------------------------------------------------------------- registry
def _load_registry() -> dict[str, DocumentInfo]:
    path = settings.registry_path
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Registry unreadable (%s); starting from an empty registry.", exc)
        return {}

    documents: dict[str, DocumentInfo] = {}
    for entry in raw.get("documents", []):
        try:
            info = DocumentInfo.model_validate(entry)
            documents[info.document_id] = info
        except Exception as exc:  # noqa: BLE001 - skip individual bad rows
            logger.warning("Skipping malformed registry entry: %s", exc)
    return documents


def _save_registry(documents: dict[str, DocumentInfo]) -> None:
    settings.ensure_directories()
    payload = {
        "version": 1,
        "documents": [
            info.model_dump(mode="json")
            for info in sorted(documents.values(), key=lambda d: d.uploaded_at)
        ],
    }
    temp = settings.registry_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(settings.registry_path)  # Atomic swap: never a half-written file.


def list_documents() -> list[DocumentInfo]:
    """Every known document, newest first."""
    with _registry_lock:
        documents = _load_registry()
    return sorted(documents.values(), key=lambda d: d.uploaded_at, reverse=True)


def get_document(document_id: str) -> DocumentInfo:
    """Look up one document.

    Raises:
        DocumentNotFoundError: if the id is unknown.
    """
    with _registry_lock:
        documents = _load_registry()
    info = documents.get(document_id)
    if info is None:
        raise DocumentNotFoundError(f"No document with id '{document_id}'.")
    return info


def _upsert(info: DocumentInfo) -> None:
    with _registry_lock:
        documents = _load_registry()
        documents[info.document_id] = info
        _save_registry(documents)


def _remove(document_id: str) -> None:
    with _registry_lock:
        documents = _load_registry()
        documents.pop(document_id, None)
        _save_registry(documents)


def total_chunks() -> int:
    """Chunk count straight from the vector store."""
    try:
        return vectorstore.count_chunks()
    except Exception:  # noqa: BLE001 - health checks must not raise
        return 0


# ------------------------------------------------------------------ ingestion
def validate_upload(filename: str, content: bytes) -> None:
    """Reject a file before anything touches disk.

    Raises:
        UnsupportedFileTypeError, InvalidFileError, FileTooLargeError.
    """
    detect_file_type(filename)  # Raises UnsupportedFileTypeError.
    if not content:
        raise InvalidFileError(f"'{filename}' is empty.")
    if len(content) > settings.max_upload_bytes:
        actual = len(content) / (1024 * 1024)
        raise FileTooLargeError(
            f"'{filename}' is {actual:.1f} MB, over the "
            f"{settings.max_upload_mb:.0f} MB limit."
        )


def _index_file(path: Path, filename: str, document_id: str) -> tuple[int, int, int]:
    """Parse, chunk and store one file. Returns (pages, chunks, characters)."""
    loaded = load_document(path, filename=filename)
    chunks = chunk_document(loaded, document_id=document_id)
    # Replace rather than append, so a re-index never leaves stale vectors.
    vectorstore.delete_document(document_id)
    vectorstore.add_chunks(chunks)
    return loaded.num_pages, len(chunks), loaded.num_characters


def ingest_document(filename: str, content: bytes) -> tuple[DocumentInfo, bool]:
    """Run the full ingestion pipeline for one uploaded file.

    Returns:
        ``(info, already_indexed)``. When the identical file is already indexed
        the work is skipped and ``already_indexed`` is ``True``.

    Raises:
        UnsupportedFileTypeError, InvalidFileError, FileTooLargeError,
        EmptyDocumentError, EmbeddingError, VectorStoreError.
    """
    validate_upload(filename, content)

    safe_name = sanitize_filename(filename)
    file_type = detect_file_type(safe_name)
    document_id = compute_document_id(content)

    # Deduplicate on content: the same bytes never get embedded twice.
    with _registry_lock:
        existing = _load_registry().get(document_id)
    if (
        existing is not None
        and existing.status == IndexStatus.INDEXED
        and vectorstore.has_document(document_id)
    ):
        logger.info("Skipping duplicate upload of '%s' (%s).", safe_name, document_id)
        return existing, True

    settings.ensure_directories()
    path = _stored_path(document_id, safe_name)
    path.write_bytes(content)

    info = DocumentInfo(
        document_id=document_id,
        filename=safe_name,
        file_type=file_type,
        size_bytes=len(content),
        status=IndexStatus.INDEXING,
        uploaded_at=_now(),
    )
    _upsert(info)

    try:
        pages, num_chunks, characters = _index_file(path, safe_name, document_id)
    except Exception:
        # A first-time upload that fails leaves nothing behind: the caller gets
        # the error, and the sidebar is not littered with an orphan entry the
        # user would have to dismiss by hand.
        vectorstore.delete_document(document_id)
        path.unlink(missing_ok=True)
        _remove(document_id)
        raise

    info.num_pages = pages
    info.num_chunks = num_chunks
    info.num_characters = characters
    info.status = IndexStatus.INDEXED
    info.indexed_at = _now()
    info.error = None
    _upsert(info)

    logger.info("Indexed '%s': %d pages, %d chunks.", safe_name, pages, num_chunks)
    return info, False


def reindex_document(document_id: str) -> DocumentInfo:
    """Re-run parsing, chunking and embedding for an already-uploaded file.

    Useful after changing the chunk size or the embedding model.

    Raises:
        DocumentNotFoundError: unknown id, or the saved file is gone.
    """
    info = get_document(document_id)
    path = _stored_path(document_id, info.filename)
    if not path.exists():
        raise DocumentNotFoundError(
            f"The stored file for '{info.filename}' is missing. Upload it again."
        )

    info.status = IndexStatus.INDEXING
    _upsert(info)
    try:
        pages, num_chunks, characters = _index_file(path, info.filename, document_id)
    except Exception as exc:  # noqa: BLE001
        info.status = IndexStatus.FAILED
        info.error = str(exc)
        _upsert(info)
        raise

    info.num_pages = pages
    info.num_chunks = num_chunks
    info.num_characters = characters
    info.status = IndexStatus.INDEXED
    info.indexed_at = _now()
    info.error = None
    _upsert(info)
    return info


# ------------------------------------------------------------------- deletion
def delete_document(document_id: str) -> int:
    """Delete a document's vectors, its stored file and its registry entry.

    Returns:
        How many vectors were removed.

    Raises:
        DocumentNotFoundError: if the id is unknown.
    """
    info = get_document(document_id)
    deleted = vectorstore.delete_document(document_id)
    _stored_path(document_id, info.filename).unlink(missing_ok=True)
    _remove(document_id)
    logger.info("Deleted '%s' (%d chunks).", info.filename, deleted)
    return deleted


def clear_documents() -> tuple[int, int]:
    """Remove every document, vector and uploaded file.

    Returns:
        ``(documents_removed, chunks_removed)``.
    """
    with _registry_lock:
        documents = _load_registry()
        count = len(documents)
        deleted_chunks = vectorstore.clear_all()
        for info in documents.values():
            _stored_path(info.document_id, info.filename).unlink(missing_ok=True)
        _save_registry({})
    logger.info("Cleared %d documents (%d chunks).", count, deleted_chunks)
    return count, deleted_chunks


# -------------------------------------------------------------- reconciliation
def reconcile_with_vectorstore() -> int:
    """Realign the registry with what ChromaDB actually holds.

    Guards against a crash between writing a vector and writing the registry.
    Returns the number of entries corrected.
    """
    with _registry_lock:
        documents = _load_registry()
        if not documents:
            return 0

        changed = 0
        for info in documents.values():
            try:
                stored = vectorstore.count_chunks(info.document_id)
            except Exception:  # noqa: BLE001 - store unavailable, leave as-is
                return 0
            if stored == 0 and info.status == IndexStatus.INDEXED:
                info.status = IndexStatus.PENDING
                info.num_chunks = 0
                info.error = "Vectors missing from the store; re-index this document."
                changed += 1
            elif stored and info.num_chunks != stored:
                info.num_chunks = stored
                info.status = IndexStatus.INDEXED
                changed += 1

        if changed:
            _save_registry(documents)
            logger.info("Reconciled %d registry entries with the vector store.", changed)
        return changed
