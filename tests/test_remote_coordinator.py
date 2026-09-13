from __future__ import annotations

import time

import pytest

from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import (
    ShardSearchError,
)
from services.search.models import SearchResult


class FakeRemoteShard:
    def __init__(
        self,
        shard_id: str,
        results: list[SearchResult],
    ) -> None:
        self.shard_id = shard_id
        self.results = results

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        return self.results[:limit]


class TransientFailureShard:
    def __init__(
        self,
        shard_id: str,
        failures_before_success: int,
    ) -> None:
        self.shard_id = shard_id
        self.failures_before_success = (
            failures_before_success
        )
        self.attempts = 0

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        self.attempts += 1

        if (
            self.attempts
            <= self.failures_before_success
        ):
            raise ShardSearchError(
                "temporary shard failure",
                retryable=True,
            )

        return [
            SearchResult(
                doc_id=99,
                score=10.0,
            )
        ]


class PermanentFailureShard:
    def __init__(
        self,
        shard_id: str,
    ) -> None:
        self.shard_id = shard_id
        self.attempts = 0

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        self.attempts += 1

        raise ShardSearchError(
            "permanent shard failure",
            retryable=False,
        )


class SlowShard:
    def __init__(
        self,
        shard_id: str,
        delay_seconds: float,
    ) -> None:
        self.shard_id = shard_id
        self.delay_seconds = delay_seconds

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        time.sleep(self.delay_seconds)
        return []


def test_coordinator_searches_remote_shards():
    shards = [
        FakeRemoteShard(
            "shard-1",
            [
                SearchResult(
                    doc_id=1,
                    score=2.0,
                )
            ],
        ),
        FakeRemoteShard(
            "shard-2",
            [
                SearchResult(
                    doc_id=2,
                    score=5.0,
                )
            ],
        ),
        FakeRemoteShard(
            "shard-3",
            [
                SearchResult(
                    doc_id=3,
                    score=3.0,
                )
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
    )

    response = coordinator.search(
        "python",
        limit=10,
    )

    assert response.total_shards == 3
    assert response.successful_shards == 3
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0

    assert [
        result.doc_id
        for result in response.results
    ] == [2, 3, 1]


def test_remote_coordinator_respects_global_limit():
    shards = [
        FakeRemoteShard(
            "shard-1",
            [
                SearchResult(
                    doc_id=1,
                    score=5.0,
                ),
                SearchResult(
                    doc_id=2,
                    score=4.0,
                ),
            ],
        ),
        FakeRemoteShard(
            "shard-2",
            [
                SearchResult(
                    doc_id=3,
                    score=3.0,
                ),
                SearchResult(
                    doc_id=4,
                    score=2.0,
                ),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
    )

    response = coordinator.search(
        "python",
        limit=2,
    )

    assert [
        result.doc_id
        for result in response.results
    ] == [1, 2]

    assert len(response.results) == 2


def test_coordinator_retries_transient_shard_failure():
    shard = TransientFailureShard(
        shard_id="shard-1",
        failures_before_success=2,
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        max_retries=2,
        retry_backoff_seconds=0,
    )

    response = coordinator.search(
        "python",
        limit=10,
    )

    assert response.successful_shards == 1
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0

    assert [
        result.doc_id
        for result in response.results
    ] == [99]

    assert shard.attempts == 3


def test_coordinator_stops_after_max_retries():
    shard = TransientFailureShard(
        shard_id="shard-1",
        failures_before_success=5,
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        max_retries=2,
        retry_backoff_seconds=0,
        allow_partial_results=True,
    )

    response = coordinator.search(
        "python",
        limit=10,
    )

    assert response.total_shards == 1
    assert response.successful_shards == 0
    assert response.failed_shards == 1
    assert response.timed_out_shards == 0
    assert response.is_partial is True

    assert response.results == []
    assert shard.attempts == 3


def test_coordinator_does_not_retry_permanent_failure():
    shard = PermanentFailureShard(
        shard_id="shard-1",
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        max_retries=5,
        retry_backoff_seconds=0,
        allow_partial_results=True,
    )

    response = coordinator.search(
        "python",
        limit=10,
    )

    assert response.total_shards == 1
    assert response.successful_shards == 0
    assert response.failed_shards == 1
    assert response.timed_out_shards == 0
    assert response.is_partial is True

    assert shard.attempts == 1


def test_coordinator_strict_mode_fails_after_retries():
    shard = TransientFailureShard(
        shard_id="shard-1",
        failures_before_success=5,
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        max_retries=2,
        retry_backoff_seconds=0,
        allow_partial_results=False,
    )

    with pytest.raises(
        RuntimeError,
        match="one or more shards were unavailable",
    ):
        coordinator.search(
            "python",
            limit=10,
        )

    assert shard.attempts == 3


def test_coordinator_timeout_remains_timeout():
    shard = SlowShard(
        shard_id="shard-1",
        delay_seconds=0.2,
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        shard_timeout_seconds=0.05,
        max_retries=2,
        retry_backoff_seconds=0,
    )

    response = coordinator.search(
        "python",
        limit=10,
    )

    assert response.successful_shards == 0
    assert response.failed_shards == 0
    assert response.timed_out_shards == 1
    assert response.is_partial is True


def test_retry_configuration_rejects_negative_retries():
    shard = FakeRemoteShard(
        "shard-1",
        [],
    )

    with pytest.raises(ValueError):
        SearchCoordinator(
            shard_clients=[shard],
            max_retries=-1,
        )


def test_retry_configuration_rejects_negative_backoff():
    shard = FakeRemoteShard(
        "shard-1",
        [],
    )

    with pytest.raises(ValueError):
        SearchCoordinator(
            shard_clients=[shard],
            retry_backoff_seconds=-1,
        )