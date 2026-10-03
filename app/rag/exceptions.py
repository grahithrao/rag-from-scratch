"""Domain exceptions.

Each carries an HTTP status so the API layer can translate a failure into a
useful message without a chain of ``isinstance`` checks.
"""

from __future__ import annotations


class RAGError(Exception):
    """Base class for every recoverable error in the pipeline."""

    status_code: int = 500
    code: str = "rag_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileTypeError(RAGError):
    status_code = 415
    code = "unsupported_file_type"


class InvalidFileError(RAGError):
    """Malformed, corrupted or unreadable upload."""

    status_code = 400
    code = "invalid_file"


class FileTooLargeError(RAGError):
    status_code = 413
    code = "file_too_large"


class EmptyDocumentError(RAGError):
    """The file parsed successfully but produced no usable text."""

    status_code = 422
    code = "empty_document"


class DocumentNotFoundError(RAGError):
    status_code = 404
    code = "document_not_found"


class EmbeddingError(RAGError):
    status_code = 503
    code = "embedding_error"


class VectorStoreError(RAGError):
    status_code = 503
    code = "vectorstore_error"


class LLMConfigurationError(RAGError):
    """No API key, or a key the provider rejects."""

    status_code = 503
    code = "llm_not_configured"


class LLMError(RAGError):
    status_code = 502
    code = "llm_error"
