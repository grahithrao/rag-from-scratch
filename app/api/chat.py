"""Retrieval and grounded-generation endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, QueryRequest, QueryResponse
from app.rag import pipeline
from app.rag.exceptions import RAGError
from app.services import document_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _require_documents() -> None:
    """Fail fast with a helpful message when nothing has been indexed yet."""
    if document_service.total_chunks() == 0:
        raise HTTPException(
            status_code=409,
            detail="No documents have been indexed yet. Upload a document first.",
        )


@router.post("/query", response_model=QueryResponse, summary="Semantic search only")
def query(request: QueryRequest) -> QueryResponse:
    """Retrieve the most relevant chunks without calling the LLM.

    Useful for inspecting exactly what the generator would be given.
    """
    _require_documents()
    try:
        return pipeline.run_retrieval(
            question=request.question,
            top_k=request.top_k,
            document_ids=request.document_ids,
        )
    except RAGError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}") from exc


@router.post("/chat", response_model=ChatResponse, summary="Ask a grounded question")
def chat(request: ChatRequest) -> ChatResponse:
    """Run the full RAG pipeline and return an answer with its citations."""
    _require_documents()
    try:
        return pipeline.run_rag(
            question=request.question,
            history=request.history,
            top_k=request.top_k,
            document_ids=request.document_ids,
        )
    except RAGError as exc:
        logger.warning("Chat failed (%s): %s", exc.code, exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat failed unexpectedly")
        raise HTTPException(
            status_code=500, detail=f"Answer generation failed: {exc}"
        ) from exc
