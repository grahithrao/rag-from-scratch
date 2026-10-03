"""The full RAG pipeline and the document service, with the LLM mocked.

Retrieval, chunking and storage run for real; only the Groq call is replaced,
so these tests verify the wiring that matters — that the model receives the
retrieved context, and that the answer ships with the chunks it was built from.
"""

from __future__ import annotations

import pytest

from app.models.schemas import ChatMessage, IndexStatus
from app.rag import generator, pipeline
from app.rag.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.rag.generator import NO_ANSWER_MESSAGE, build_messages, generate_answer
from app.services import document_service

pytestmark = pytest.mark.usefixtures("isolated_storage")


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeGroqClient:
    """Records the payload it is called with so tests can inspect the prompt."""

    def __init__(self, reply: str = "The computer ran at 2.048 MHz [Source 1].") -> None:
        self.reply = reply
        self.calls: list[dict] = []
        outer = self

        class Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return FakeCompletion(outer.reply)

        class Chat:
            completions = Completions()

        self.chat = Chat()


@pytest.fixture()
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeGroqClient:
    client = FakeGroqClient()
    monkeypatch.setattr(generator, "_get_client", lambda: client)
    return client


@pytest.fixture()
def indexed_txt(sample_text: str) -> str:
    info, _ = document_service.ingest_document("apollo.txt", sample_text.encode("utf-8"))
    return info.document_id


# --------------------------------------------------------------- ingestion
class TestIngestion:
    def test_indexes_a_text_document(self, sample_text: str) -> None:
        info, already = document_service.ingest_document(
            "apollo.txt", sample_text.encode("utf-8")
        )

        assert already is False
        assert info.status is IndexStatus.INDEXED
        assert info.num_chunks > 0
        assert info.num_characters > 0
        assert info.indexed_at is not None

    def test_indexes_a_real_pdf_with_page_metadata(self, pdf_file) -> None:
        info, _ = document_service.ingest_document("apollo.pdf", pdf_file.read_bytes())

        assert info.status is IndexStatus.INDEXED
        assert info.num_pages == 2
        pages = {source.page for source in pipeline.run_retrieval("Apollo", top_k=10).sources}
        assert pages <= {1, 2}

    def test_identical_content_is_not_indexed_twice(self, sample_text: str) -> None:
        content = sample_text.encode("utf-8")
        first, _ = document_service.ingest_document("apollo.txt", content)
        second, already = document_service.ingest_document("apollo.txt", content)

        assert already is True
        assert second.document_id == first.document_id
        assert len(document_service.list_documents()) == 1

    def test_rejects_unsupported_type(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            document_service.ingest_document("photo.png", b"\x89PNG data")

    def test_rejects_oversized_upload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "max_upload_mb", 0.0001)
        with pytest.raises(FileTooLargeError):
            document_service.ingest_document("big.txt", b"x" * 10_000)

    @pytest.mark.parametrize(
        ("raw", "forbidden"),
        [("../../etc/passwd", ".."), ("/tmp/evil.txt", "/"), ("a\\b\\c.txt", "\\")],
    )
    def test_sanitises_path_traversal_in_filenames(self, raw: str, forbidden: str) -> None:
        assert forbidden not in document_service.sanitize_filename(raw)

    def test_content_hash_is_the_document_id(self) -> None:
        a = document_service.compute_document_id(b"same bytes")
        b = document_service.compute_document_id(b"same bytes")
        c = document_service.compute_document_id(b"other bytes")

        assert a == b != c


# ------------------------------------------------------------- management
class TestDocumentManagement:
    def test_delete_removes_document_and_vectors(self, indexed_txt: str) -> None:
        from app.rag import vectorstore

        deleted = document_service.delete_document(indexed_txt)

        assert deleted > 0
        assert vectorstore.count_chunks(indexed_txt) == 0
        assert document_service.list_documents() == []
        with pytest.raises(DocumentNotFoundError):
            document_service.get_document(indexed_txt)

    def test_delete_unknown_id_raises(self) -> None:
        with pytest.raises(DocumentNotFoundError):
            document_service.delete_document("nope")

    def test_clear_removes_everything(self, indexed_txt: str, sample_text: str) -> None:
        document_service.ingest_document("second.txt", (sample_text + " extra").encode())
        documents, chunks = document_service.clear_documents()

        assert documents == 2
        assert chunks > 0
        assert document_service.total_chunks() == 0

    def test_reindex_rebuilds_chunks_without_duplicating(self, indexed_txt: str) -> None:
        before = document_service.get_document(indexed_txt).num_chunks
        info = document_service.reindex_document(indexed_txt)

        assert info.status is IndexStatus.INDEXED
        assert info.num_chunks == before
        assert document_service.total_chunks() == before

    def test_registry_survives_a_restart(self, indexed_txt: str) -> None:
        from app.rag import vectorstore

        vectorstore.reset_store()  # Simulates the API process restarting.
        documents = document_service.list_documents()

        assert len(documents) == 1
        assert documents[0].document_id == indexed_txt
        assert documents[0].status is IndexStatus.INDEXED


# ---------------------------------------------------------------- prompting
class TestPromptConstruction:
    def test_context_and_question_reach_the_model(self, indexed_txt: str) -> None:
        sources = pipeline.run_retrieval("Apollo computer", top_k=2).sources
        messages = build_messages("What is the clock speed?", sources)

        assert messages[0]["role"] == "system"
        assert "never use outside knowledge" in messages[0]["content"].lower()
        assert "[Source 1]" in messages[-1]["content"]
        assert "What is the clock speed?" in messages[-1]["content"]

    def test_history_is_included_but_trimmed(self, indexed_txt: str) -> None:
        from app.config import settings

        sources = pipeline.run_retrieval("Apollo", top_k=1).sources
        history = [
            ChatMessage(role="user" if i % 2 == 0 else "assistant", content=f"turn {i}")
            for i in range(20)
        ]
        messages = build_messages("Follow up?", sources, history)

        # system + at most max_history_turns*2 history entries + the question
        assert len(messages) <= 2 + settings.max_history_turns * 2
        assert "turn 19" in messages[-2]["content"]


# ----------------------------------------------------------------- pipeline
class TestRAGPipeline:
    def test_answer_is_generated_from_retrieved_context(
        self, indexed_txt: str, fake_llm: FakeGroqClient
    ) -> None:
        response = pipeline.run_rag("What clock speed did the Apollo computer run at?")

        assert response.grounded is True
        assert response.sources, "a grounded answer must ship its citations"
        assert "2.048 MHz" in response.answer
        assert response.generation_ms >= 0

        # The context the model saw must be the retrieved text, not the raw question.
        sent = fake_llm.calls[0]["messages"][-1]["content"]
        assert "Apollo Guidance Computer" in sent

    def test_citations_come_from_the_store_not_the_model(
        self, indexed_txt: str, fake_llm: FakeGroqClient
    ) -> None:
        response = pipeline.run_rag("Who led the software effort?")

        for source in response.sources:
            assert source.document_id == indexed_txt
            assert source.filename == "apollo.txt"
            assert 0.0 <= source.score <= 1.0

    def test_no_relevant_context_refuses_without_calling_the_llm(
        self, indexed_txt: str, fake_llm: FakeGroqClient
    ) -> None:
        result = generate_answer("Unanswerable question", sources=[])

        assert result.grounded is False
        assert NO_ANSWER_MESSAGE in result.answer
        assert fake_llm.calls == [], "the LLM must not be called with empty context"

    def test_empty_store_yields_an_ungrounded_refusal(self, fake_llm: FakeGroqClient) -> None:
        response = pipeline.run_rag("Anything?")

        assert response.grounded is False
        assert response.sources == []
        assert NO_ANSWER_MESSAGE in response.answer

    def test_retrieval_is_independent_of_generation(
        self, indexed_txt: str, fake_llm: FakeGroqClient
    ) -> None:
        response = pipeline.run_retrieval("Apollo Guidance Computer", top_k=3)

        assert response.sources
        assert fake_llm.calls == [], "run_retrieval must never invoke the LLM"

    def test_blank_model_reply_falls_back_to_the_refusal(
        self, indexed_txt: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = FakeGroqClient(reply="   ")
        monkeypatch.setattr(generator, "_get_client", lambda: client)

        assert NO_ANSWER_MESSAGE in pipeline.run_rag("Apollo?").answer
