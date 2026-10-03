"""Text extraction from PDF, DOCX and TXT, including the failure paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.schemas import FileType
from app.rag.exceptions import (
    EmptyDocumentError,
    InvalidFileError,
    UnsupportedFileTypeError,
)
from app.rag.loader import detect_file_type, load_document, normalise_text


class TestDetectFileType:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("report.pdf", FileType.PDF),
            ("REPORT.PDF", FileType.PDF),
            ("notes.docx", FileType.DOCX),
            ("readme.txt", FileType.TXT),
            ("readme.md", FileType.TXT),
        ],
    )
    def test_supported_extensions(self, filename: str, expected: FileType) -> None:
        assert detect_file_type(filename) is expected

    @pytest.mark.parametrize("filename", ["image.png", "archive.zip", "legacy.doc", "noext"])
    def test_rejects_unsupported(self, filename: str) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            detect_file_type(filename)


class TestNormaliseText:
    def test_collapses_whitespace_and_blank_lines(self) -> None:
        assert normalise_text("a    b\n\n\n\nc") == "a b\n\nc"

    def test_rejoins_words_hyphenated_across_lines(self) -> None:
        assert "retrieval" in normalise_text("retri-\neval augmented")

    def test_normalises_windows_line_endings(self) -> None:
        assert "\r" not in normalise_text("line one\r\nline two")


class TestLoadTxt:
    def test_extracts_text_with_metadata(self, txt_file: Path) -> None:
        document = load_document(txt_file)

        assert document.file_type is FileType.TXT
        assert document.num_pages == 1
        assert "Apollo Guidance Computer" in document.full_text
        assert document.pages[0].metadata["filename"] == "apollo.txt"

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.txt"
        path.write_text("   \n\n  ", encoding="utf-8")
        with pytest.raises(EmptyDocumentError):
            load_document(path)


class TestLoadPdf:
    def test_extracts_every_page_with_page_numbers(self, pdf_file: Path) -> None:
        document = load_document(pdf_file)

        assert document.file_type is FileType.PDF
        assert document.num_pages == 2
        assert [page.page for page in document.pages] == [1, 2]
        assert "Apollo" in document.full_text
        assert document.num_characters > 100

    def test_corrupted_pdf_raises_invalid_file(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.pdf"
        path.write_bytes(b"%PDF-1.4 this is not really a pdf at all")
        with pytest.raises((InvalidFileError, EmptyDocumentError)):
            load_document(path)


class TestLoadDocx:
    def test_extracts_paragraphs(self, docx_file: Path) -> None:
        document = load_document(docx_file)

        assert document.file_type is FileType.DOCX
        assert "Apollo Guidance Computer" in document.full_text
        assert document.pages[0].page == 1

    def test_non_docx_content_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "fake.docx"
        path.write_bytes(b"not a zip archive")
        with pytest.raises(InvalidFileError):
            load_document(path)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileError):
        load_document(tmp_path / "does_not_exist.txt")
