"""Semantic retrieval — deliberately separate from generation.

Turns a question into ranked, de-duplicated :class:`SourceChunk` citations. The
generator consumes the result but never performs a search itself, so retrieval
can be tested and inspected on its own (``POST /query``).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from langchain_core.documents import Document

from app.config import settings
from app.models.schemas import SourceChunk
from app.rag import vectorstore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievalResult:
    """Ranked chunks for one question, plus timing for the UI."""

    question: str
    sources: list[SourceChunk]
    elapsed_ms: float

    @property
    def is_empty(self) -> bool:
        return not self.sources


def distance_to_score(distance: float) -> float:
    """Map cosine distance in [0, 2] to a 0-1 relevance score."""
    return max(0.0, min(1.0, 1.0 - (distance / 2.0)))


def _to_source(document: Document, distance: float) -> SourceChunk:
    metadata = document.metadata or {}
    page = metadata.get("page")
    return SourceChunk(
        document_id=str(metadata.get("document_id", "unknown")),
        filename=str(metadata.get("filename", "unknown")),
        file_type=str(metadata.get("file_type", "unknown")),
        page=int(page) if isinstance(page, (int, float)) else None,
        chunk_index=int(metadata.get("chunk_index", 0)),
        text=document.page_content,
        score=round(distance_to_score(distance), 4),
    )


def retrieve(
    question: str,
    top_k: int | None = None,
    document_ids: list[str] | None = None,
    max_distance: float | None = None,
) -> RetrievalResult:
    """Find the chunks most relevant to ``question``.

    Over-fetches, filters out weak matches beyond ``max_distance``, drops
    duplicate chunks, then keeps the best ``top_k``.

    Args:
        question: The user's natural-language question.
        top_k: How many chunks to return. Defaults to ``settings.top_k``.
        document_ids: Restrict the search to these documents.
        max_distance: Cosine-distance ceiling for a match to count.
    """
    started = time.perf_counter()
    k = top_k or settings.top_k
    ceiling = max_distance if max_distance is not None else settings.max_distance

    # Over-fetch so the distance filter has candidates to spare.
    raw = vectorstore.similarity_search(
        question, k=min(k * 3, 60), document_ids=document_ids
    )

    seen: set[str] = set()
    sources: list[SourceChunk] = []
    for document, distance in sorted(raw, key=lambda pair: pair[1]):
        if distance > ceiling:
            continue
        metadata = document.metadata or {}
        key = f"{metadata.get('document_id')}:{metadata.get('chunk_index')}"
        if key in seen:
            continue
        seen.add(key)
        sources.append(_to_source(document, distance))
        if len(sources) >= k:
            break

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Retrieved %d/%d candidate chunks in %.0f ms", len(sources), len(raw), elapsed_ms
    )
    return RetrievalResult(
        question=question, sources=sources, elapsed_ms=round(elapsed_ms, 2)
    )


def format_context(sources: list[SourceChunk]) -> str:
    """Render retrieved chunks as the numbered context block sent to the LLM.

    The numbering matches the "Source N" cards in the UI, so a citation in the
    generated answer points at something the user can actually open.
    """
    blocks: list[str] = []
    for position, source in enumerate(sources, start=1):
        location = f", page {source.page}" if source.page else ""
        blocks.append(
            f"[Source {position}] (file: {source.filename}{location})\n{source.text}"
        )
    return "\n\n---\n\n".join(blocks)
