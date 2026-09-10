from services.indexer.index import InvertedIndex
from services.search.engine import SearchEngine


def build_test_index() -> InvertedIndex:
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=[
            "python",
            "python",
            "search",
            "engine",
        ],
    )

    index.add_document(
        doc_id=2,
        tokens=[
            "python",
            "database",
        ],
    )

    index.add_document(
        doc_id=3,
        tokens=[
            "distributed",
            "systems",
        ],
    )

    index.add_document(
        doc_id=4,
        tokens=[
            "python",
            "search",
        ],
    )

    return index


def test_search_returns_ranked_results():
    index = build_test_index()

    engine = SearchEngine(index)

    results = engine.search("python")

    assert results
    assert all(result.score >= 0 for result in results)

    scores = [result.score for result in results]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_search_result_contains_document_id_and_score():
    index = build_test_index()

    engine = SearchEngine(index)

    results = engine.search("python")

    assert all(
        isinstance(result.doc_id, int)
        for result in results
    )

    assert all(
        isinstance(result.score, float)
        for result in results
    )


def test_search_respects_limit():
    index = build_test_index()

    engine = SearchEngine(index)

    results = engine.search(
        "python",
        limit=2,
    )

    assert len(results) == 2


def test_search_multiple_terms():
    index = build_test_index()

    engine = SearchEngine(index)

    results = engine.search(
        "python search"
    )

    result_ids = {
        result.doc_id
        for result in results
    }

    assert result_ids == {1, 2, 4}

def test_search_unknown_term_returns_empty():
    index = build_test_index()

    engine = SearchEngine(index)

    results = engine.search(
        "javascript"
    )

    assert results == []


def test_search_empty_query_returns_empty():
    index = build_test_index()

    engine = SearchEngine(index)

    assert engine.search("") == []


def test_search_stopword_only_query_returns_empty():
    index = build_test_index()

    engine = SearchEngine(index)

    assert engine.search("the and or") == []


def test_search_zero_limit_returns_empty():
    index = build_test_index()

    engine = SearchEngine(index)

    assert engine.search(
        "python",
        limit=0,
    ) == []


def test_search_negative_limit_returns_empty():
    index = build_test_index()

    engine = SearchEngine(index)

    assert engine.search(
        "python",
        limit=-1,
    ) == []


def test_search_results_are_deterministic_for_equal_scores():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python"],
    )

    index.add_document(
        doc_id=2,
        tokens=["python"],
    )

    engine = SearchEngine(index)

    results = engine.search("python")

    result_ids = [
        result.doc_id
        for result in results
    ]

    assert result_ids == [1, 2]