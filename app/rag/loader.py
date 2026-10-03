"""Document loading: bytes on disk -> page-level text with metadata.

Each loader returns a list of :class:`LoadedPage`. Keeping the page boundary at
this stage is what later lets a citation say "page 7" instead of just naming the
file.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.models.schemas import FileType
from app.rag.exceptions import (
    EmptyDocumentError,
    InvalidFileError,
    UnsupportedFileTypeError,
)

SUPPORTED_EXTENSIONS: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".txt": FileType.TXT,
    ".md": FileType.TXT,
    ".markdown": FileType.TXT,
}

_WHITESPACE_RUN = re.compile(r"[ \t   ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
# Soft hyphen + newline: PDFs break words across lines, glue them back together.
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


@dataclass(slots=True)
class LoadedPage:
    """Text of a single page (or logical section) plus its provenance."""

    text: str
    page: int
    metadata: dict[str, str | int] = field(default_factory=dict)


@dataclass(slots=True)
class LoadedDocument:
    """The full result of parsing one file."""

    filename: str
    file_type: FileType
    pages: list[LoadedPage]

    @property
    def num_pages(self) -> int:
        return len(self.pages)

    @property
    def num_characters(self) -> int:
        return sum(len(page.text) for page in self.pages)

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


def normalise_text(raw: str) -> str:
    """Collapse the whitespace noise that PDF and DOCX extraction leaves behind."""
    text = unicodedata.normalize("NFKC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _WHITESPACE_RUN.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def detect_file_type(filename: str) -> FileType:
    """Map a filename to a supported :class:`FileType`.

    Raises:
        UnsupportedFileTypeError: if the extension is not one we can parse.
    """
    suffix = Path(filename).suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(suffix)
    if file_type is None:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"'{suffix or filename}' is not supported. Supported types: {supported}."
        )
    return file_type


def _load_pdf(path: Path, name: str) -> list[LoadedPage]:
    import pymupdf  # PyMuPDF; imported lazily so tests can skip it.

    try:
        document = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 - surface any parser failure uniformly
        raise InvalidFileError(
            f"Could not open '{name}'. The PDF appears to be corrupted, truncated "
            f"or password protected."
        ) from exc

    pages: list[LoadedPage] = []
    try:
        if document.is_encrypted and not document.authenticate(""):
            raise InvalidFileError(
                f"'{name}' is password protected and cannot be indexed."
            )
        for index, page in enumerate(document, start=1):
            try:
                text = normalise_text(page.get_text("text"))
            except Exception:  # noqa: BLE001 - one bad page must not kill the file
                continue
            if text:
                pages.append(LoadedPage(text=text, page=index))
    finally:
        document.close()
    return pages


def _load_docx(path: Path, name: str) -> list[LoadedPage]:
    import docx
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = docx.Document(str(path))
    except PackageNotFoundError as exc:
        raise InvalidFileError(
            f"'{name}' is not a valid .docx file. Legacy .doc files are not "
            f"supported — re-save it as .docx."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise InvalidFileError(f"Could not read '{name}': {exc}") from exc

    blocks: list[str] = [
        para.text.strip() for para in document.paragraphs if para.text.strip()
    ]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    text = normalise_text("\n\n".join(blocks))
    # DOCX has no reliable page concept without rendering; treat it as one page.
    return [LoadedPage(text=text, page=1)] if text else []


def _load_txt(path: Path, name: str) -> list[LoadedPage]:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            raw = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise InvalidFileError(f"Could not read '{name}': {exc}") from exc
    else:
        raise InvalidFileError(
            f"'{name}' is not readable as text - it may be a binary file."
        )

    text = normalise_text(raw)
    return [LoadedPage(text=text, page=1)] if text else []


_LOADERS: dict[FileType, Callable[[Path, str], list[LoadedPage]]] = {
    FileType.PDF: _load_pdf,
    FileType.DOCX: _load_docx,
    FileType.TXT: _load_txt,
}


def load_document(path: Path, filename: str | None = None) -> LoadedDocument:
    """Parse ``path`` into pages of clean text.

    Args:
        path: Location of the saved upload.
        filename: Original filename, used for type detection and metadata when
            the stored path has been sanitised.

    Raises:
        UnsupportedFileTypeError: unknown extension.
        InvalidFileError: unreadable or corrupted file.
        EmptyDocumentError: parsed fine but contains no extractable text.
    """
    display_name = filename or path.name
    file_type = detect_file_type(display_name)

    if not path.exists():
        raise InvalidFileError(f"File not found on disk: {path}")

    pages = _LOADERS[file_type](path, display_name)
    if not pages:
        raise EmptyDocumentError(
            f"No text could be extracted from '{display_name}'. Scanned or "
            f"image-only documents need OCR, which this MVP does not perform."
        )

    for page in pages:
        page.metadata.update({"filename": display_name, "file_type": file_type.value})

    return LoadedDocument(filename=display_name, file_type=file_type, pages=pages)
