from services.search.coordinator import (
    SearchCoordinator,
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