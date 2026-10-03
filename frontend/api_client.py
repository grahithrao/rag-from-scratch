"""Thin HTTP client for the FastAPI backend.

The frontend never touches ChromaDB, the embedding model or the Groq key
directly — every secret and every heavy dependency stays server-side.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001")

UPLOAD_TIMEOUT = 300  # Embedding a large PDF is slow the first time.
CHAT_TIMEOUT = 120
DEFAULT_TIMEOUT = 30


class APIError(Exception):
    """A backend error already phrased for a human reader."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(slots=True)
class RAGClient:
    """Typed wrapper around the backend's REST endpoints."""

    base_url: str = DEFAULT_BASE_URL

    # ---------------------------------------------------------------- internals
    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        try:
            response = requests.request(method, self._url(path), **kwargs)
        except requests.exceptions.ConnectionError as exc:
            raise APIError(
                f"Cannot reach the backend at {self.base_url}. Start it with: "
                f"uvicorn app.main:app --port 8001"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise APIError(
                "The backend took too long to respond. Try again, or use a smaller "
                "document."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise APIError(f"Request failed: {exc}") from exc

        if response.status_code >= 400:
            raise APIError(self._extract_detail(response), response.status_code)

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise APIError("The backend returned a malformed response.") from exc

    @staticmethod
    def _extract_detail(response: requests.Response) -> str:
        """Pull a readable message out of a FastAPI or validation error body."""
        try:
            payload = response.json()
        except ValueError:
            return f"Backend error (HTTP {response.status_code})."

        detail = payload.get("detail", payload)
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:  # Pydantic validation errors.
            first = detail[0]
            if isinstance(first, dict):
                field = " → ".join(str(part) for part in first.get("loc", [])[1:])
                message = first.get("msg", "Invalid request.")
                return f"{field}: {message}" if field else str(message)
        return f"Backend error (HTTP {response.status_code})."

    # ----------------------------------------------------------------- system
    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", timeout=10)

    def config(self) -> dict[str, Any]:
        return self._request("GET", "/config", timeout=10)

    # -------------------------------------------------------------- documents
    def list_documents(self) -> dict[str, Any]:
        return self._request("GET", "/documents")

    def upload_document(self, filename: str, content: bytes, mime: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/documents/upload",
            files={"file": (filename, content, mime or "application/octet-stream")},
            timeout=UPLOAD_TIMEOUT,
        )

    def delete_document(self, document_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/documents/{document_id}", timeout=60)

    def clear_documents(self) -> dict[str, Any]:
        return self._request("DELETE", "/documents", timeout=60)

    def reindex_document(self, document_id: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/documents/reindex/{document_id}", timeout=UPLOAD_TIMEOUT
        )

    # ------------------------------------------------------------------- chat
    def chat(
        self,
        question: str,
        history: list[dict[str, str]] | None = None,
        top_k: int | None = None,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"question": question, "history": history or []}
        if top_k is not None:
            payload["top_k"] = top_k
        if document_ids:
            payload["document_ids"] = document_ids
        return self._request("POST", "/chat", json=payload, timeout=CHAT_TIMEOUT)

    def query(self, question: str, top_k: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"question": question}
        if top_k is not None:
            payload["top_k"] = top_k
        return self._request("POST", "/query", json=payload, timeout=CHAT_TIMEOUT)
