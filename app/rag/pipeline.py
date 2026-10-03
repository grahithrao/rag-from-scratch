"""The RAG pipeline — the seam where retrieval meets generation.

Two entry points mirror the two API endpoints:

* :func:`run_retrieval` — question -> ranked chunks (no LLM involved).
* :func:`run_rag` — question -> retrieved chunks -> grounded answer + citations.

Both are thin by design; the real work lives in :mod:`app.rag.retriever` and
:mod:`app.rag.generator` so either half can be swapped or tested in isolation.
"""

from __future__ import annotations

import logging

from app.models.schemas import ChatMessage, ChatResponse, QueryResponse
from app.rag import generator, retriever

logger = logging.getLogger(__name__)


def run_retrieval(
    question: str,
    top_k: int | None = None,
    document_ids: list[str] | None = None,
) -> QueryResponse:
    """Retrieve the chunks most relevant to ``question`` without generating."""
    result = retriever.retrieve(question, top_k=top_k, document_ids=document_ids)
    return QueryResponse(
        question=question, sources=result.sources, retrieval_ms=result.elapsed_ms
    )


def run_rag(
    question: str,
    history: list[ChatMessage] | None = None,
    top_k: int | None = None,
    document_ids: list[str] | None = None,
) -> ChatResponse:
    """Run the full pipeline: retrieve, ground, generate, cite.

    Returns:
        A :class:`ChatResponse` whose ``sources`` are exactly the chunks that
        were fed to the model — never a fabricated citation list.
    """
    retrieval = retriever.retrieve(question, top_k=top_k, document_ids=document_ids)
    generation = generator.generate_answer(
        question=question, sources=retrieval.sources, history=history
    )
    return ChatResponse(
        question=question,
        answer=generation.answer,
        # A failed grounding returns no sources, so the UI shows no citations.
        sources=retrieval.sources if generation.grounded else [],
        grounded=generation.grounded,
        model=generation.model,
        retrieval_ms=retrieval.elapsed_ms,
        generation_ms=generation.elapsed_ms,
    )
