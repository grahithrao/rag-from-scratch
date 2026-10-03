"""End-to-end storage and retrieval against a real ChromaDB collection.

These use the real embedding model — no mocks — because the thing worth testing
is that semantic search actually ranks relevant text above irrelevant text.
"""

from __future__ import annotations

import pytest

from app.rag import vectorstore
from app.rag.chunker import Chunk
from app.rag.retriever import distance_to_score, format_context, retrieve

pytestmark = pytest.mark.usefixtures("isolated_storage")


def make_chunk(index: int, text: str, document_id: str = "doc1", page: int = 1) -> Chunk:
    return Chunk(
        id=f"{document_id}:{index}",
        text=text,
        document_id=document_id,
        filename=f"{document_id}.txt",
        file_type="txt",
        page=page,
        chunk_index=index,
    )


@pytest.fixture()
def populated_store() -> None:
    """Three clearly distinct topics, so ranking assertions are unambiguous."""
    vectorstore.add_chunks(
        [
            make_chunk(0, "The Apollo Guidance Computer ran at 2.048 MHz and used "
                          "magnetic-core rope memory for the Apollo missions.", page=1),
            make_chunk(1, "Margaret Hamilton led the software engineering team at the "
                          "MIT Instrumentation Laboratory.", page=2),
            make_chunk(2, "Photosynthesis converts light energy into chemical energy "
                          "inside plant chloroplasts.", document_id="doc2", page=1),
        ]
    )


class TestVectorStore:
    def test_add_and_count(self) -> None:
        assert vectorstore.count_chunks() == 0
        written = vectorstore.add_chunks([make_chunk(0, "Some indexable content here.")])

        assert written == 1
        assert vectorstore.count_chunks() == 1
        assert vectorstore.has_document("doc1")

    def test_adding_nothing_is_a_no_op(self) -> None:
        assert vectorstore.add_chunks([]) == 0

    def test_similarity_search_returns_documents_and_distances(self, populated_store) -> None:
        results = vectorstore.similarity_search("guidance computer memory", k=3)

        assert results
        document, distance = results[0]
        assert isinstance(distance, float)
        assert document.metadata["document_id"] in {"doc1", "doc2"}

    def test_filter_restricts_search_to_one_document(self, populated_store) -> None:
        results = vectorstore.similarity_search("anything", k=5, document_ids=["doc2"])

        assert results
        assert all(doc.metadata["document_id"] == "doc2" for doc, _ in results)

    def test_delete_document_removes_only_its_vectors(self, populated_store) -> None:
        deleted = vectorstore.delete_document("doc1")

        assert deleted == 2
        assert vectorstore.count_chunks("doc1") == 0
        assert vectorstore.count_chunks("doc2") == 1
        assert not vectorstore.has_document("doc1")

    def test_clear_all_empties_the_collection(self, populated_store) -> None:
        assert vectorstore.clear_all() == 3
        assert vectorstore.count_chunks() == 0

    def test_data_survives_reopening_the_store(self, populated_store) -> None:
        vectorstore.reset_store()  # Simulates an API restart.
        assert vectorstore.count_chunks() == 3


class TestScoring:
    @pytest.mark.parametrize(
        ("distance", "expected"), [(0.0, 1.0), (1.0, 0.5), (2.0, 0.0), (3.0, 0.0)]
    )
    def test_distance_maps_into_unit_range(self, distance: float, expected: float) -> None:
        assert distance_to_score(distance) == pytest.approx(expected)


class TestRetrieve:
    def test_ranks_relevant_chunks_above_irrelevant_ones(self, populated_store) -> None:
        result = retrieve("What clock speed did the Apollo computer run at?", top_k=3)

        assert not result.is_empty
        assert result.sources[0].document_id == "doc1"
        assert "2.048 MHz" in result.sources[0].text
        assert result.elapsed_ms >= 0

    def test_scores_are_sorted_descending(self, populated_store) -> None:
        result = retrieve("Apollo software engineering", top_k=3)
        scores = [source.score for source in result.sources]

        assert scores == sorted(scores, reverse=True)
        assert all(0.0 <= score <= 1.0 for score in scores)

    def test_metadata_survives_the_round_trip(self, populated_store) -> None:
        source = retrieve("magnetic core rope memory", top_k=1).sources[0]

        assert source.filename == "doc1.txt"
        assert source.file_type == "txt"
        assert source.page == 1
        assert source.chunk_index == 0

    def test_top_k_caps_the_result_count(self, populated_store) -> None:
        assert len(retrieve("computer", top_k=2).sources) <= 2

    def test_document_filter_is_honoured(self, populated_store) -> None:
        result = retrieve("Apollo computer", top_k=5, document_ids=["doc2"])

        assert all(source.document_id == "doc2" for source in result.sources)

    def test_strict_distance_threshold_filters_everything_out(self, populated_store) -> None:
        result = retrieve("Apollo", top_k=5, max_distance=0.0)

        assert result.is_empty

    def test_empty_store_returns_no_sources(self) -> None:
        assert retrieve("anything at all", top_k=5).is_empty


class TestFormatContext:
    def test_numbers_sources_and_includes_pages(self, populated_store) -> None:
        context = format_context(retrieve("Apollo computer", top_k=2).sources)

        assert "[Source 1]" in context
        assert "page" in context
        assert "doc1.txt" in context

    def test_empty_sources_produce_empty_context(self) -> None:
        assert format_context([]) == ""
