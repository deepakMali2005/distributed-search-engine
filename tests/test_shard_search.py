import pytest

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard


def create_shard() -> Shard:
    return Shard(
        shard_id="shard-1",
        index=InvertedIndex(),
    )


def test_shard_search_returns_matching_documents():
    shard = create_shard()

    shard.add_document(
        doc_id=1,
        tokens=[
            "python",
            "distributed",
            "systems",
        ],
    )

    shard.add_document(
        doc_id=2,
        tokens=[
            "javascript",
            "frontend",
        ],
    )

    results = shard.search("python")

    assert len(results) == 1
    assert results[0].doc_id == 1


def test_shard_search_only_searches_local_documents():
    shard = create_shard()

    shard.add_document(
        doc_id=1,
        tokens=[
            "python",
            "search",
        ],
    )

    results = shard.search(
        "javascript"
    )

    assert results == []


def test_shard_search_respects_limit():
    shard = create_shard()

    for doc_id in range(1, 6):
        shard.add_document(
            doc_id=doc_id,
            tokens=["python"],
        )

    results = shard.search(
        "python",
        limit=2,
    )

    assert len(results) == 2


def test_empty_query_returns_no_results():
    shard = create_shard()

    shard.add_document(
        doc_id=1,
        tokens=["python"],
    )

    results = shard.search("")

    assert results == []


def test_invalid_limit_raises():
    shard = create_shard()

    with pytest.raises(ValueError):
        shard.search(
            "python",
            limit=0,
        )