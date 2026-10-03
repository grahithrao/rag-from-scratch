"""Chunking: page text -> overlapping windows sized for the embedding model.

Metadata (document id, filename, page, chunk index) is attached here and travels
untouched through embeddings, storage and retrieval, which is what makes the
citations at the end of the pipeline trustworthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag.exceptions import EmptyDocumentError
from app.rag.loader import LoadedDocument

# Ordered coarse -> fine: split on paragraphs first, fall back to characters only
# when a single "word" is longer than the window.
_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]


@dataclass(slots=True)
class Chunk:
    """A single embeddable unit of text with full provenance."""

    id: str
    text: str
    document_id: str
    filename: str
    file_type: str
    page: int
    chunk_index: int
    metadata: dict[str, str | int] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, str | int]:
        """Flatten to the primitive-only mapping Chroma accepts."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "page": self.page,
            "chunk_index": self.chunk_index,
            **self.metadata,
        }


def build_splitter(
    chunk_size: int | None = None, chunk_overlap: int | None = None
) -> RecursiveCharacterTextSplitter:
    """Create the configured recursive splitter."""
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    return RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=_SEPARATORS,
        length_function=len,
        keep_separator=True,
    )


def chunk_document(
    document: LoadedDocument,
    document_id: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split every page of ``document`` into overlapping chunks.

    Chunk indices are continuous across the whole document, so a chunk id is
    unique and stable for a given document.

    Raises:
        EmptyDocumentError: when splitting yields nothing usable.
    """
    splitter = build_splitter(chunk_size, chunk_overlap)
    chunks: list[Chunk] = []
    index = 0

    for page in document.pages:
        for piece in splitter.split_text(page.text):
            text = piece.strip()
            if len(text) < 24:  # Drop page numbers, stray headers, empty splits.
                continue
            chunks.append(
                Chunk(
                    id=f"{document_id}:{index}",
                    text=text,
                    document_id=document_id,
                    filename=document.filename,
                    file_type=document.file_type.value,
                    page=page.page,
                    chunk_index=index,
                )
            )
            index += 1

    if not chunks:
        raise EmptyDocumentError(
            f"'{document.filename}' produced no usable chunks — the extracted text "
            f"is too short to index."
        )
    return chunks
