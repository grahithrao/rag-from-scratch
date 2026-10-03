"""Smoke tests for the Streamlit UI.

These render the real app with the HTTP layer stubbed out. They exist because a
rendering error — an invalid avatar, a bad format string, a missing session key —
does not show up in any backend test but breaks the app for the user.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
sys.path.insert(0, str(FRONTEND))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = str(FRONTEND / "streamlit_app.py")

HEALTH = {
    "status": "ok",
    "version": "1.0.0",
    "llm_configured": True,
    "llm_model": "openai/gpt-oss-120b",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_ready": True,
    "vectorstore_ready": True,
    "indexed_documents": 1,
    "indexed_chunks": 5,
    "detail": None,
}
CONFIG = {
    "llm_model": "openai/gpt-oss-120b",
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "chunk_size": 1000,
    "chunk_overlap": 150,
    "top_k": 5,
    "max_upload_mb": 25.0,
    "supported_types": ["docx", "md", "pdf", "txt"],
}
DOCUMENTS = {
    "documents": [
        {
            "document_id": "abc123",
            "filename": "report.pdf",
            "file_type": "pdf",
            "size_bytes": 8011,
            "num_pages": 5,
            "num_chunks": 5,
            "num_characters": 3407,
            "status": "indexed",
            "error": None,
            "uploaded_at": "2026-01-01T00:00:00Z",
            "indexed_at": "2026-01-01T00:00:01Z",
        }
    ],
    "total_documents": 1,
    "total_chunks": 5,
}
ANSWER = {
    "question": "What is this document about?",
    "answer": "It is a **deployment report**.\n\n1. First point\n2. Second point",
    "sources": [
        {
            "document_id": "abc123",
            "filename": "report.pdf",
            "file_type": "pdf",
            "page": 3,
            "chunk_index": 2,
            "text": "The hallucination rate was measured at 2.1 percent.",
            "score": 0.72,
        }
    ],
    "grounded": True,
    "model": "openai/gpt-oss-120b",
    "retrieval_ms": 11.0,
    "generation_ms": 1443.0,
}


@pytest.fixture()
def stub_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace every network call with a canned response."""
    import api_client

    monkeypatch.setattr(api_client.RAGClient, "health", lambda self: HEALTH)
    monkeypatch.setattr(api_client.RAGClient, "config", lambda self: CONFIG)
    monkeypatch.setattr(api_client.RAGClient, "list_documents", lambda self: DOCUMENTS)
    monkeypatch.setattr(
        api_client.RAGClient, "chat", lambda self, **kwargs: ANSWER
    )


def render(**kwargs: Any) -> Any:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


class TestInitialRender:
    def test_app_renders_without_exceptions(self, stub_api: None) -> None:
        at = render()
        assert not at.exception, [str(e.value) for e in at.exception]

    def test_header_and_empty_state_are_present(self, stub_api: None) -> None:
        markdown = " ".join(m.value for m in render().markdown)

        assert "RAG From Scratch" in markdown
        assert "System ready" in markdown
        assert "Your documents, now searchable." in markdown
        assert "Upload a document and ask a question" in markdown

    def test_indexed_document_is_listed_in_the_sidebar(self, stub_api: None) -> None:
        markdown = " ".join(m.value for m in render().markdown)

        assert "report.pdf" in markdown
        assert "5 chunks" in markdown
        assert "Indexed" in markdown

    def test_example_questions_are_offered(self, stub_api: None) -> None:
        labels = [button.label for button in render().button]

        assert "What is this document about?" in labels
        assert "Summarize the main points." in labels
        assert "What are the key conclusions?" in labels

    def test_chat_input_is_enabled_when_documents_exist(self, stub_api: None) -> None:
        assert render().chat_input[0].disabled is False


class TestAnswerFlow:
    def test_asking_a_question_renders_answer_and_sources(self, stub_api: None) -> None:
        at = render()
        button = next(b for b in at.button if b.label == "What is this document about?")

        button.click().run()
        at.run()  # Second pass answers the queued question.

        assert not at.exception, [str(e.value) for e in at.exception]
        markdown = " ".join(m.value for m in at.markdown)
        assert 'class="ask"' in markdown        # user turn
        assert 'class="say"' in markdown        # assistant turn
        assert "Sources ·" in markdown          # citation header
        assert "report.pdf" in markdown
        assert "p.3" in markdown                # page reference
        assert "72%" in markdown                # match score
        assert "gpt-oss-120b" in markdown       # meta line

    def test_chat_avatars_are_renderable(self, stub_api: None) -> None:
        """Guards a real bug: a dingbat such as U+2726 looks like an emoji but is
        not one, so Streamlit falls back to loading it as an image path and the
        whole assistant message throws. Material Symbols avoid the ambiguity."""
        from streamlit.string_util import validate_icon_or_emoji

        import streamlit_app

        avatars = {streamlit_app.USER_ICON, streamlit_app.ASSISTANT_ICON}
        assert avatars, "expected the app to set explicit chat avatars"
        for avatar in avatars:
            validate_icon_or_emoji(avatar)  # Raises for anything unrenderable.

    def test_button_icons_are_valid_material_symbols(self, stub_api: None) -> None:
        """Every st.button(icon=...) name must exist, or the widget throws."""
        import re

        from streamlit.string_util import validate_material_icon

        source = Path(APP).read_text(encoding="utf-8")
        icons = set(re.findall(r'icon="(:material/[a-z_]+:)"', source))

        assert icons, "expected the app to use Material Symbol button icons"
        for icon in icons:
            validate_material_icon(icon)


class TestDegradedBackend:
    def test_missing_api_key_shows_a_warning_not_a_crash(
        self, stub_api: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import api_client

        degraded = {**HEALTH, "status": "degraded", "llm_configured": False,
                    "detail": "GROQ_API_KEY is not configured."}
        monkeypatch.setattr(api_client.RAGClient, "health", lambda self: degraded)

        at = render()

        assert not at.exception
        assert any("GROQ_API_KEY" in w.value for w in at.warning)

    def test_unreachable_backend_shows_instructions_not_a_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import api_client

        def boom(self):
            raise api_client.APIError("Cannot reach the backend at http://127.0.0.1:8001")

        monkeypatch.setattr(api_client.RAGClient, "health", boom)

        at = render()

        assert not at.exception
        assert any("Cannot reach the backend" in e.value for e in at.error)
