import pytest

from services.indexer.index import InvertedIndex
from services.search.models import AnalyzedQuery
from services.search.ranking import BM25Ranker


def test_rank_returns_scores_for_candidates():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "python", "search"],
    )

    index.add_document(
        doc_id=2,
        tokens=["database", "search"],
    )

    ranker = BM25Ranker(index)

    query = AnalyzedQuery(
        terms=("python",)
    )

    scores = ranker.rank(
        query=query,
        candidate_doc_ids={1},
    )

    assert 1 in scores
    assert scores[1] > 0


def test_document_with_more_term_occurrences_scores_higher():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "python", "python"],
    )

    index.add_document(
        doc_id=2,
        tokens=["python"],
    )

    ranker = BM25Ranker(index)

    query = AnalyzedQuery(
        terms=("python",)
    )

    scores = ranker.rank(
        query=query,
        candidate_doc_ids={1, 2},
    )

    assert scores[1] > scores[2]


def test_empty_query_returns_empty_scores():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python"],
    )

    ranker = BM25Ranker(index)

    query = AnalyzedQuery(terms=())

    scores = ranker.rank(
        query=query,
        candidate_doc_ids={1},
    )

    assert scores == {}


def test_no_candidates_returns_empty_scores():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python"],
    )

    ranker = BM25Ranker(index)

    query = AnalyzedQuery(
        terms=("python",)
    )

    scores = ranker.rank(
        query=query,
        candidate_doc_ids=set(),
    )

    assert scores == {}


def test_unknown_term_does_not_produce_score():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python"],
    )

    ranker = BM25Ranker(index)

    query = AnalyzedQuery(
        terms=("database",)
    )

    scores = ranker.rank(
        query=query,
        candidate_doc_ids={1},
    )

    assert scores[1] == pytest.approx(0.0)


def test_multiple_query_terms_contribute_to_score():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    index.add_document(
        doc_id=2,
        tokens=["python"],
    )

    ranker = BM25Ranker(index)

    query = AnalyzedQuery(
        terms=("python", "search")
    )

    scores = ranker.rank(
        query=query,
        candidate_doc_ids={1, 2},
    )

    assert scores[1] > scores[2]