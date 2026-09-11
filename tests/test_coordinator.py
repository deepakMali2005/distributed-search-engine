import time

import pytest

from services.indexer.shard_manager import ShardManager
from services.search.coordinator import (
    SearchCoordinator,
    ShardSearchOutcome,
)
from services.search.models import SearchResult


def create_coordinator(
    *,
    timeout: float = 2.0,
    allow_partial_results: bool = True,
) -> SearchCoordinator:
    manager = ShardManager(
        [
            "shard-1",
            "shard-2",
            "shard-3",
        ]
    )

    return SearchCoordinator(
        manager,
        shard_timeout_seconds=timeout,
        allow_partial_results=allow_partial_results,
    )


def test_searches_all_shards():
    coordinator = create_coordinator()

    manager = coordinator.shard_manager

    manager.index_document(
        document_id=1,
        tokens=["python", "distributed"],
    )

    manager.index_document(
        document_id=2,
        tokens=["python", "search"],
    )

    manager.index_document(
        document_id=3,
        tokens=["javascript", "frontend"],
    )

    response = coordinator.search("python")

    result_ids = {
        result.doc_id
        for result in response.results
    }

    assert result_ids == {1, 2}

    assert response.total_shards == 3
    assert response.successful_shards == 3
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0


def test_results_are_globally_sorted():
    coordinator = create_coordinator()

    manager = coordinator.shard_manager

    manager.index_document(
        document_id=1,
        tokens=["python"],
    )

    manager.index_document(
        document_id=2,
        tokens=[
            "python",
            "python",
            "python",
        ],
    )

    response = coordinator.search(
        "python"
    )

    results = response.results

    assert len(results) == 2
    assert results[0].score >= results[1].score


def test_coordinator_respects_global_limit():
    coordinator = create_coordinator()

    manager = coordinator.shard_manager

    for doc_id in range(1, 11):
        manager.index_document(
            document_id=doc_id,
            tokens=["python"],
        )

    response = coordinator.search(
        "python",
        limit=3,
    )

    assert len(response.results) == 3


def test_empty_query_returns_no_results():
    coordinator = create_coordinator()

    response = coordinator.search("")

    assert response.results == []


def test_invalid_limit_raises():
    coordinator = create_coordinator()

    with pytest.raises(ValueError):
        coordinator.search(
            "python",
            limit=0,
        )


def test_duplicate_document_keeps_highest_score():
    coordinator = create_coordinator()

    outcomes = [
        ShardSearchOutcome(
            shard_id="shard-1",
            results=[
                SearchResult(
                    doc_id=1,
                    score=2.0,
                )
            ],
        ),
        ShardSearchOutcome(
            shard_id="shard-2",
            results=[
                SearchResult(
                    doc_id=1,
                    score=5.0,
                )
            ],
        ),
    ]

    results = coordinator._merge_results(
        outcomes=outcomes,
        limit=10,
    )

    assert len(results) == 1
    assert results[0].doc_id == 1
    assert results[0].score == 5.0


def test_shard_failure_produces_partial_results():
    coordinator = create_coordinator()

    manager = coordinator.shard_manager

    manager.index_document(
        document_id=1,
        tokens=["python"],
    )

    failing_shard = manager.get_shard(
        "shard-1"
    )

    original_search = failing_shard.search

    def failing_search(
        query: str,
        limit: int,
    ):
        raise RuntimeError(
            "Shard unavailable"
        )

    failing_shard.search = failing_search

    try:
        response = coordinator.search(
            "python"
        )

        assert response.failed_shards == 1
        assert response.successful_shards == 2
        assert response.is_partial is True
    finally:
        failing_shard.search = original_search


def test_shard_timeout_produces_partial_results():
    coordinator = create_coordinator(
        timeout=0.05
    )

    manager = coordinator.shard_manager

    manager.index_document(
        document_id=1,
        tokens=["python"],
    )

    slow_shard = manager.get_shard(
        "shard-1"
    )

    original_search = slow_shard.search

    def slow_search(
        query: str,
        limit: int,
    ):
        time.sleep(0.2)
        return []

    slow_shard.search = slow_search

    try:
        response = coordinator.search(
            "python"
        )

        assert response.timed_out_shards == 1
        assert response.successful_shards == 2
        assert response.is_partial is True
    finally:
        slow_shard.search = original_search


def test_strict_mode_rejects_partial_results():
    coordinator = create_coordinator(
        allow_partial_results=False
    )

    manager = coordinator.shard_manager

    failing_shard = manager.get_shard(
        "shard-1"
    )

    original_search = failing_shard.search

    def failing_search(
        query: str,
        limit: int,
    ):
        raise RuntimeError(
            "Shard unavailable"
        )

    failing_shard.search = failing_search

    try:
        with pytest.raises(RuntimeError):
            coordinator.search(
                "python"
            )
    finally:
        failing_shard.search = original_search
