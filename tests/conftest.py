"""Shared fixtures.

Every test runs against a temporary upload directory, Chroma path and registry,
so the suite never touches the developer's real indexed documents.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Must be set before app.config is imported anywhere.
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")


@pytest.fixture(scope="session")
def sample_text() -> str:
    return (
        "The Apollo Guidance Computer was developed at the MIT Instrumentation "
        "Laboratory for the Apollo program. It ran at 2.048 MHz and had 2 kilowords "
        "of erasable magnetic-core memory plus 36 kilowords of read-only rope memory. "
        "Margaret Hamilton led the software engineering effort.\n\n"
        "The computer's priority-scheduled executive was critical during the Apollo 11 "
        "landing, when repeated 1202 and 1201 alarms indicated an overloaded processor. "
        "Because low-priority jobs were shed automatically, the landing continued "
        "safely. This restart protection is often cited as an early triumph of "
        "software fault tolerance.\n\n"
        "Photosynthesis is unrelated to spaceflight and appears here only so that "
        "retrieval tests have an off-topic paragraph to rank lower than the rest."
    )


@pytest.fixture()
def txt_file(tmp_path: Path, sample_text: str) -> Path:
    path = tmp_path / "apollo.txt"
    path.write_text(sample_text, encoding="utf-8")
    return path


@pytest.fixture()
def pdf_file(tmp_path: Path, sample_text: str) -> Path:
    """A real two-page PDF built with PyMuPDF."""
    pymupdf = pytest.importorskip("pymupdf")
    document = pymupdf.open()
    paragraphs = sample_text.split("\n\n")
    for index, paragraph in enumerate(paragraphs[:2]):
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(56, 56, 540, 740),
            f"Page {index + 1}\n\n{paragraph}",
            fontsize=11,
        )
    path = tmp_path / "apollo.pdf"
    document.save(path)
    document.close()
    return path


@pytest.fixture()
def docx_file(tmp_path: Path, sample_text: str) -> Path:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Apollo Guidance Computer", level=1)
    for paragraph in sample_text.split("\n\n"):
        document.add_paragraph(paragraph)
    path = tmp_path / "apollo.docx"
    document.save(path)
    return path


@pytest.fixture()
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point config at a throwaway directory and reset the cached singletons."""
    from app.config import settings
    from app.rag import vectorstore

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "chroma_dir", tmp_path / "chroma")
    monkeypatch.setattr(settings, "registry_path", tmp_path / "registry.json")
    monkeypatch.setattr(settings, "chroma_collection", "test_collection")
    settings.ensure_directories()

    vectorstore.reset_store()
    yield tmp_path
    vectorstore.reset_store()
