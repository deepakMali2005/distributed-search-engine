import pytest

from services.search.hybrid import HybridRanker


def test_hybrid_rank_combines_lexical_and_semantic_scores():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={
            1: 10.0,
            2: 5.0,
        },
        semantic_scores={
            1: 0.5,
            2: 0.9,
        },
        limit=10,
    )

    assert [result.doc_id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(0.5)
    assert results[1].score == pytest.approx(0.5)


def test_hybrid_rank_includes_documents_found_by_only_one_retriever():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={1: 10.0},
        semantic_scores={2: 0.9},
    )

    assert {result.doc_id for result in results} == {1, 2}
    assert results[0].score == pytest.approx(0.5)
    assert results[1].score == pytest.approx(0.5)


def test_hybrid_rank_respects_custom_weights():
    ranker = HybridRanker(
        lexical_weight=0.8,
        semantic_weight=0.2,
    )

    results = ranker.rank(
        lexical_scores={
            1: 10.0,
            2: 5.0,
        },
        semantic_scores={
            1: 0.5,
            2: 0.9,
        },
    )

    assert [result.doc_id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(0.8)
    assert results[1].score == pytest.approx(0.2)


def test_hybrid_rank_normalizes_weights():
    ranker = HybridRanker(
        lexical_weight=8.0,
        semantic_weight=2.0,
    )

    assert ranker.lexical_weight == pytest.approx(0.8)
    assert ranker.semantic_weight == pytest.approx(0.2)


def test_hybrid_rank_uses_zero_for_missing_retrieval_score():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={
            1: 10.0,
            2: 5.0,
        },
        semantic_scores={
            1: 0.9,
        },
    )

    assert [result.doc_id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(0.0)


def test_hybrid_rank_handles_negative_scores():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={
            1: -0.5,
            2: -1.5,
        },
        semantic_scores={},
    )

    assert [result.doc_id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(0.5)
    assert results[1].score == pytest.approx(0.0)


def test_hybrid_rank_returns_empty_for_no_candidates():
    ranker = HybridRanker()

    assert ranker.rank({}, {}) == []


def test_hybrid_rank_respects_limit():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={
            1: 10.0,
            2: 9.0,
            3: 8.0,
        },
        semantic_scores={},
        limit=2,
    )

    assert [result.doc_id for result in results] == [1, 2]


def test_hybrid_rank_uses_doc_id_as_deterministic_tie_breaker():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={
            3: 1.0,
            1: 1.0,
            2: 1.0,
        },
        semantic_scores={},
    )

    assert [result.doc_id for result in results] == [1, 2, 3]


def test_hybrid_rank_all_equal_scores_have_no_ranking_signal():
    ranker = HybridRanker()

    results = ranker.rank(
        lexical_scores={
            1: 4.0,
            2: 4.0,
        },
        semantic_scores={},
    )

    assert [result.doc_id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(0.0)
    assert results[1].score == pytest.approx(0.0)


@pytest.mark.parametrize(
    "lexical_weight, semantic_weight",
    [
        (-1.0, 1.0),
        (1.0, -1.0),
        (0.0, 0.0),
        (float("inf"), 1.0),
        (1.0, float("nan")),
    ],
)
def test_hybrid_rank_rejects_invalid_weights(
    lexical_weight: float,
    semantic_weight: float,
):
    with pytest.raises(ValueError):
        HybridRanker(
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
        )


def test_hybrid_rank_rejects_non_finite_scores():
    ranker = HybridRanker()

    with pytest.raises(ValueError):
        ranker.rank(
            lexical_scores={1: float("inf")},
            semantic_scores={},
        )