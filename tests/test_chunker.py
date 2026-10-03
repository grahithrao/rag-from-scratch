"""Chunking behaviour and — critically — metadata preservation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rag.chunker import build_splitter, chunk_document
from app.rag.exceptions import EmptyDocumentError
from app.rag.loader import LoadedDocument, LoadedPage, load_document
from app.models.schemas import FileType


def make_document(pages: list[str], filename: str = "test.txt") -> LoadedDocument:
    return LoadedDocument(
        filename=filename,
        file_type=FileType.TXT,
        pages=[LoadedPage(text=text, page=i) for i, text in enumerate(pages, start=1)],
    )


class TestSplitter:
    def test_respects_configured_size(self) -> None:
        splitter = build_splitter(chunk_size=200, chunk_overlap=20)
        pieces = splitter.split_text("word " * 400)

        assert len(pieces) > 1
        # The recursive splitter may overshoot slightly on separator boundaries.
        assert all(len(piece) <= 260 for piece in pieces)

    def test_overlap_must_be_smaller_than_size(self) -> None:
        with pytest.raises(ValueError):
            build_splitter(chunk_size=100, chunk_overlap=100)


class TestChunkDocument:
    def test_produces_chunks_with_stable_ids(self, sample_text: str) -> None:
        chunks = chunk_document(
            make_document([sample_text]), document_id="doc123",
            chunk_size=300, chunk_overlap=50,
        )

        assert len(chunks) > 1
        assert [c.id for c in chunks] == [f"doc123:{i}" for i in range(len(chunks))]
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_preserves_page_numbers_across_pages(self) -> None:
        long_a, long_b = "Alpha content. " * 60, "Beta content. " * 60
        chunks = chunk_document(
            make_document([long_a, long_b]), document_id="doc",
            chunk_size=200, chunk_overlap=20,
        )

        pages = {chunk.page for chunk in chunks}
        assert pages == {1, 2}
        # Every chunk drawn from page 2 must contain page-2 text, not page-1 text.
        assert all("Beta" in c.text for c in chunks if c.page == 2)

    def test_chunk_index_is_continuous_across_pages(self) -> None:
        chunks = chunk_document(
            make_document(["Alpha. " * 60, "Beta. " * 60]), document_id="doc",
            chunk_size=200, chunk_overlap=20,
        )
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_metadata_is_complete_and_primitive(self, sample_text: str) -> None:
        chunks = chunk_document(
            make_document([sample_text], filename="apollo.txt"), document_id="abc"
        )
        metadata = chunks[0].to_metadata()

        assert metadata["document_id"] == "abc"
        assert metadata["filename"] == "apollo.txt"
        assert metadata["file_type"] == "txt"
        assert metadata["page"] == 1
        assert metadata["chunk_index"] == 0
        # Chroma only accepts primitives in metadata.
        assert all(isinstance(v, (str, int, float, bool)) for v in metadata.values())

    def test_overlap_creates_shared_text_between_neighbours(self) -> None:
        text = " ".join(f"sentence{i}." for i in range(200))
        chunks = chunk_document(
            make_document([text]), document_id="doc", chunk_size=300, chunk_overlap=100
        )

        assert len(chunks) > 2
        tail = chunks[0].text[-40:].strip()
        assert any(word in chunks[1].text for word in tail.split() if word)

    def test_text_too_short_raises(self) -> None:
        with pytest.raises(EmptyDocumentError):
            chunk_document(make_document(["tiny"]), document_id="doc")

    def test_real_pdf_chunks_carry_correct_pages(self, pdf_file: Path) -> None:
        document = load_document(pdf_file)
        chunks = chunk_document(document, document_id="pdfdoc", chunk_size=300, chunk_overlap=50)

        assert chunks
        assert {c.page for c in chunks} <= {1, 2}
        assert all(c.file_type == "pdf" for c in chunks)
        assert all(c.filename == "apollo.pdf" for c in chunks)
