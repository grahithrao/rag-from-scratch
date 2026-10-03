"""HTTP surface: status codes, payload shapes and error messages."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag import generator
from tests.test_pipeline import FakeGroqClient

pytestmark = pytest.mark.usefixtures("isolated_storage")


@pytest.fixture()
def client() -> TestClient:
    # Plain constructor, not a context manager: the lifespan warm-up would open
    # the real (non-isolated) Chroma directory.
    return TestClient(app)


class TestSystemEndpoints:
    def test_health_reports_component_readiness(self, client: TestClient) -> None:
        response = client.get("/health")
        body = response.json()

        assert response.status_code == 200
        assert body["status"] in {"ok", "degraded"}
        assert body["embedding_ready"] is True
        assert body["vectorstore_ready"] is True
        assert "version" in body

    def test_config_never_leaks_the_api_key(self, client: TestClient) -> None:
        body = client.get("/config").json()

        assert body["top_k"] >= 1
        assert "pdf" in body["supported_types"]
        assert not any("key" in key.lower() for key in body)


class TestDocumentEndpoints:
    def test_list_is_empty_initially(self, client: TestClient) -> None:
        body = client.get("/documents").json()

        assert body["documents"] == []
        assert body["total_documents"] == 0

    def test_upload_indexes_and_lists_the_document(
        self, client: TestClient, sample_text: str
    ) -> None:
        response = client.post(
            "/documents/upload",
            files={"file": ("apollo.txt", sample_text.encode(), "text/plain")},
        )
        body = response.json()

        assert response.status_code == 201
        assert body["already_indexed"] is False
        assert body["document"]["status"] == "indexed"
        assert body["document"]["num_chunks"] > 0

        listing = client.get("/documents").json()
        assert listing["total_documents"] == 1
        assert listing["total_chunks"] == body["document"]["num_chunks"]

    def test_duplicate_upload_is_reported_not_reindexed(
        self, client: TestClient, sample_text: str
    ) -> None:
        files = {"file": ("apollo.txt", sample_text.encode(), "text/plain")}
        client.post("/documents/upload", files=files)
        second = client.post(
            "/documents/upload",
            files={"file": ("apollo.txt", sample_text.encode(), "text/plain")},
        ).json()

        assert second["already_indexed"] is True
        assert client.get("/documents").json()["total_documents"] == 1

    def test_unsupported_type_returns_415(self, client: TestClient) -> None:
        response = client.post(
            "/documents/upload", files={"file": ("bad.png", b"\x89PNG", "image/png")}
        )

        assert response.status_code == 415
        assert "not supported" in response.json()["detail"]

    def test_empty_file_returns_400(self, client: TestClient) -> None:
        response = client.post(
            "/documents/upload", files={"file": ("empty.txt", b"", "text/plain")}
        )
        assert response.status_code == 400

    def test_delete_removes_document_and_chunks(
        self, client: TestClient, sample_text: str
    ) -> None:
        upload = client.post(
            "/documents/upload",
            files={"file": ("apollo.txt", sample_text.encode(), "text/plain")},
        ).json()
        document_id = upload["document"]["document_id"]

        response = client.delete(f"/documents/{document_id}")

        assert response.status_code == 200
        assert response.json()["deleted_chunks"] > 0
        assert client.get("/documents").json()["total_chunks"] == 0

    def test_delete_unknown_id_returns_404(self, client: TestClient) -> None:
        assert client.delete("/documents/missing").status_code == 404

    def test_reindex_returns_the_updated_document(
        self, client: TestClient, sample_text: str
    ) -> None:
        upload = client.post(
            "/documents/upload",
            files={"file": ("apollo.txt", sample_text.encode(), "text/plain")},
        ).json()
        document_id = upload["document"]["document_id"]

        response = client.post(f"/documents/reindex/{document_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "indexed"

    def test_clear_all_empties_the_store(self, client: TestClient, sample_text: str) -> None:
        client.post(
            "/documents/upload",
            files={"file": ("apollo.txt", sample_text.encode(), "text/plain")},
        )
        response = client.delete("/documents")

        assert response.status_code == 200
        assert response.json()["deleted_documents"] == 1
        assert client.get("/documents").json()["total_documents"] == 0


class TestChatEndpoints:
    @pytest.fixture()
    def indexed(self, client: TestClient, sample_text: str) -> TestClient:
        client.post(
            "/documents/upload",
            files={"file": ("apollo.txt", sample_text.encode(), "text/plain")},
        )
        return client

    def test_query_returns_sources_without_generating(self, indexed: TestClient) -> None:
        body = indexed.post("/query", json={"question": "Apollo clock speed?"}).json()

        assert body["sources"]
        assert "answer" not in body
        assert body["sources"][0]["filename"] == "apollo.txt"

    def test_chat_returns_a_grounded_answer_with_citations(
        self, indexed: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(generator, "_get_client", lambda: FakeGroqClient())

        body = indexed.post(
            "/chat",
            json={
                "question": "What clock speed did the Apollo computer run at?",
                "history": [],
            },
        ).json()

        assert body["grounded"] is True
        assert "2.048 MHz" in body["answer"]
        assert body["sources"]
        assert body["retrieval_ms"] >= 0

    def test_chat_accepts_conversation_history(
        self, indexed: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = FakeGroqClient()
        monkeypatch.setattr(generator, "_get_client", lambda: fake)

        indexed.post(
            "/chat",
            json={
                "question": "Explain that in more detail.",
                "history": [
                    {"role": "user", "content": "What is the main topic?"},
                    {"role": "assistant", "content": "The Apollo Guidance Computer."},
                ],
            },
        )

        contents = [m["content"] for m in fake.calls[0]["messages"]]
        assert "What is the main topic?" in contents

    def test_query_without_documents_returns_409(self, client: TestClient) -> None:
        response = client.post("/query", json={"question": "anything"})

        assert response.status_code == 409
        assert "Upload a document" in response.json()["detail"]

    def test_blank_question_is_rejected(self, indexed: TestClient) -> None:
        assert indexed.post("/chat", json={"question": "   "}).status_code == 422

    def test_missing_api_key_returns_a_helpful_503(
        self, indexed: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "groq_api_key", "")
        generator.reset_client()

        response = indexed.post("/chat", json={"question": "Apollo clock speed?"})

        assert response.status_code == 503
        assert "GROQ_API_KEY" in response.json()["detail"]
