import pytest

from services.semantic.models import Embedding
from services.semantic.vector_index import VectorIndex


def test_vector_index_starts_empty() -> None:
    index = VectorIndex()

    assert index.document_count == 0
    assert index.document_ids == set()


def test_add_document_stores_embedding() -> None:
    index = VectorIndex()
    embedding = Embedding([1.0, 2.0, 3.0])

    index.add_document(
        doc_id=1,
        embedding=embedding,
    )

    assert index.document_count == 1
    assert index.document_ids == {1}
    assert index.contains_document(1)
    assert index.get_embedding(1) == embedding
    assert index.dimension == 3


def test_add_document_replaces_existing_embedding() -> None:
    index = VectorIndex()

    first = Embedding([1.0, 0.0])
    replacement = Embedding([0.0, 1.0])

    index.add_document(
        doc_id=1,
        embedding=first,
    )

    index.add_document(
        doc_id=1,
        embedding=replacement,
    )

    assert index.document_count == 1
    assert index.get_embedding(1) == replacement


def test_add_document_rejects_invalid_document_id() -> None:
    index = VectorIndex()
    embedding = Embedding([1.0, 0.0])

    with pytest.raises(
        ValueError,
        match="doc_id must be greater than zero",
    ):
        index.add_document(
            doc_id=0,
            embedding=embedding,
        )

    with pytest.raises(
        ValueError,
        match="doc_id must be greater than zero",
    ):
        index.add_document(
            doc_id=-1,
            embedding=embedding,
        )


def test_index_dimension_is_set_by_first_embedding() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 2.0, 3.0]),
    )

    assert index.dimension == 3


def test_index_rejects_different_embedding_dimension() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 2.0]),
    )

    with pytest.raises(
        ValueError,
        match="Embedding dimension does not match",
    ):
        index.add_document(
            doc_id=2,
            embedding=Embedding([1.0, 2.0, 3.0]),
        )


def test_remove_document_removes_embedding() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 0.0]),
    )

    index.remove_document(1)

    assert index.document_count == 0
    assert index.document_ids == set()
    assert not index.contains_document(1)
    assert index.get_embedding(1) is None


def test_remove_missing_document_is_noop() -> None:
    index = VectorIndex()

    index.remove_document(999)

    assert index.document_count == 0


def test_search_returns_results_by_similarity() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 0.0]),
    )
    index.add_document(
        doc_id=2,
        embedding=Embedding([0.0, 1.0]),
    )
    index.add_document(
        doc_id=3,
        embedding=Embedding([1.0, 1.0]),
    )

    results = index.search(
        query_embedding=Embedding([1.0, 0.0]),
        top_k=3,
    )

    assert [result.doc_id for result in results] == [
        1,
        3,
        2,
    ]

    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(
        1 / (2**0.5)
    )
    assert results[2].score == pytest.approx(0.0)


def test_search_returns_top_k_only() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 0.0]),
    )
    index.add_document(
        doc_id=2,
        embedding=Embedding([0.9, 0.1]),
    )
    index.add_document(
        doc_id=3,
        embedding=Embedding([0.8, 0.2]),
    )

    results = index.search(
        query_embedding=Embedding([1.0, 0.0]),
        top_k=2,
    )

    assert len(results) == 2
    assert [result.doc_id for result in results] == [
        1,
        2,
    ]


def test_search_is_deterministic_for_equal_scores() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=2,
        embedding=Embedding([0.0, 1.0]),
    )
    index.add_document(
        doc_id=1,
        embedding=Embedding([0.0, 1.0]),
    )

    results = index.search(
        query_embedding=Embedding([0.0, 1.0]),
        top_k=2,
    )

    assert [result.doc_id for result in results] == [
        1,
        2,
    ]


def test_search_empty_index_returns_empty_list() -> None:
    index = VectorIndex()

    results = index.search(
        query_embedding=Embedding([1.0, 0.0]),
        top_k=10,
    )

    assert results == []


def test_search_rejects_invalid_top_k() -> None:
    index = VectorIndex()

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        index.search(
            query_embedding=Embedding([1.0, 0.0]),
            top_k=0,
        )

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        index.search(
            query_embedding=Embedding([1.0, 0.0]),
            top_k=-1,
        )


def test_search_rejects_query_dimension_mismatch() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 0.0]),
    )

    with pytest.raises(
        ValueError,
        match="Query embedding dimension does not match",
    ):
        index.search(
            query_embedding=Embedding(
                [1.0, 0.0, 0.0]
            ),
            top_k=10,
        )


def test_clear_removes_all_embeddings() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 0.0]),
    )
    index.add_document(
        doc_id=2,
        embedding=Embedding([0.0, 1.0]),
    )

    index.clear()

    assert index.document_count == 0
    assert index.document_ids == set()
    assert not index.contains_document(1)
    assert not index.contains_document(2)


def test_dimension_after_clear_requires_embeddings() -> None:
    index = VectorIndex()

    index.add_document(
        doc_id=1,
        embedding=Embedding([1.0, 0.0]),
    )

    index.clear()

    with pytest.raises(
        ValueError,
        match="Vector index has no embeddings",
    ):
        index.dimension