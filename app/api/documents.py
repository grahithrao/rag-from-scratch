"""Document management endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings
from app.models.schemas import (
    ClearResponse,
    DeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    UploadResponse,
)
from app.rag.exceptions import RAGError
from app.services import document_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse, summary="List indexed documents")
def list_documents() -> DocumentListResponse:
    """Return every known document plus store-wide totals."""
    documents = document_service.list_documents()
    return DocumentListResponse(
        documents=documents,
        total_documents=len(documents),
        total_chunks=document_service.total_chunks(),
    )


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a document",
)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """Validate, store, parse, chunk, embed and index one file.

    Uploading a file whose contents are already indexed is a no-op and reports
    ``already_indexed``.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename supplied.")

    try:
        content = await file.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Could not read the uploaded file: {exc}"
        ) from exc
    finally:
        await file.close()

    try:
        info, already_indexed = document_service.ingest_document(file.filename, content)
    except RAGError as exc:
        logger.warning("Upload rejected (%s): %s", exc.code, exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure while indexing '%s'", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Indexing failed unexpectedly: {exc}"
        ) from exc

    message = (
        f"'{info.filename}' is already indexed ({info.num_chunks} chunks)."
        if already_indexed
        else f"Indexed '{info.filename}' into {info.num_chunks} chunks."
    )
    return UploadResponse(
        document=info, already_indexed=already_indexed, message=message
    )


@router.delete(
    "/{document_id}", response_model=DeleteResponse, summary="Delete one document"
)
def delete_document(document_id: str) -> DeleteResponse:
    """Remove a document's vectors, its stored file and its registry entry."""
    try:
        info = document_service.get_document(document_id)
        deleted = document_service.delete_document(document_id)
    except RAGError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DeleteResponse(
        document_id=document_id,
        deleted_chunks=deleted,
        message=f"Deleted '{info.filename}' and {deleted} chunks.",
    )


@router.delete("", response_model=ClearResponse, summary="Delete every document")
def clear_documents() -> ClearResponse:
    """Wipe the collection, the registry and every stored upload."""
    try:
        documents, chunks = document_service.clear_documents()
    except RAGError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ClearResponse(
        deleted_documents=documents,
        deleted_chunks=chunks,
        message=f"Removed {documents} documents and {chunks} chunks.",
    )


@router.post(
    "/reindex/{document_id}",
    response_model=DocumentInfo,
    summary="Re-chunk and re-embed a document",
)
def reindex_document(document_id: str) -> DocumentInfo:
    """Re-run ingestion for a stored file, e.g. after changing chunk settings."""
    try:
        return document_service.reindex_document(document_id)
    except RAGError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Re-index failed for %s", document_id)
        raise HTTPException(status_code=500, detail=f"Re-index failed: {exc}") from exc
