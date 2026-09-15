from __future__ import annotations

from fastapi.testclient import TestClient

from services.search.coordinator import SearchResponse
from services.search.models import SearchResult
from services.search_api import main


class FakeCoordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

        self.lexical_response = SearchResponse(
            results=[
                SearchResult(
                    doc_id=1,
                    score=2.5,
                ),
                SearchResult(
                    doc_id=2,
                    score=1.5,
                ),
            ],
            total_shards=3,
            successful_shards=3,
            failed_shards=0,
            timed_out_shards=0,
        )

        self.semantic_response = SearchResponse(
            results=[
                SearchResult(
                    doc_id=3,
                    score=0.95,
                ),
            ],
            total_shards=3,
            successful_shards=3,
            failed_shards=0,
            timed_out_shards=0,
        )

        self.hybrid_response = SearchResponse(
            results=[
                SearchResult(
                    doc_id=4,
                    score=0.91,
                ),
                SearchResult(
                    doc_id=5,
                    score=0.82,
                ),
            ],
            total_shards=3,
            successful_shards=3,
            failed_shards=0,
            timed_out_shards=0,
        )

    def search(
        self,
        query: str,
        limit: int,
    ) -> SearchResponse:
        self.calls.append(
            (
                "lexical",
                query,
                limit,
            )
        )

        return self.lexical_response

    def semantic_search(
        self,
        query: str,
        limit: int,
    ) -> SearchResponse:
        self.calls.append(
            (
                "semantic",
                query,
                limit,
            )
        )

        return self.semantic_response

    def hybrid_search(
        self,
        query: str,
        limit: int,
    ) -> SearchResponse:
        self.calls.append(
            (
                "hybrid",
                query,
                limit,
            )
        )

        return self.hybrid_response


def _client_with_fake_coordinator(
    fake_coordinator: FakeCoordinator,
) -> TestClient:
    main.search_coordinator = fake_coordinator

    return TestClient(
        main.app,
        raise_server_exceptions=True,
    )


def test_search_endpoint_defaults_to_hybrid():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "distributed search",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "distributed search"
    assert body["mode"] == "hybrid"

    assert body["results"] == [
        {
            "doc_id": 4,
            "score": 0.91,
        },
        {
            "doc_id": 5,
            "score": 0.82,
        },
    ]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 3
    assert body["failed_shards"] == 0
    assert body["timed_out_shards"] == 0
    assert body["partial"] is False

    assert fake.calls == [
        (
            "hybrid",
            "distributed search",
            10,
        ),
    ]


def test_search_endpoint_supports_lexical_mode():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "python",
            "mode": "lexical",
            "limit": 5,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "python"
    assert body["mode"] == "lexical"

    assert body["results"] == [
        {
            "doc_id": 1,
            "score": 2.5,
        },
        {
            "doc_id": 2,
            "score": 1.5,
        },
    ]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 3
    assert body["failed_shards"] == 0
    assert body["timed_out_shards"] == 0
    assert body["partial"] is False

    assert fake.calls == [
        (
            "lexical",
            "python",
            5,
        ),
    ]


def test_search_endpoint_supports_semantic_mode():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "machine learning",
            "mode": "semantic",
            "limit": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "machine learning"
    assert body["mode"] == "semantic"

    assert body["results"] == [
        {
            "doc_id": 3,
            "score": 0.95,
        },
    ]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 3
    assert body["failed_shards"] == 0
    assert body["timed_out_shards"] == 0
    assert body["partial"] is False

    assert fake.calls == [
        (
            "semantic",
            "machine learning",
            3,
        ),
    ]


def test_search_endpoint_returns_complete_distributed_response():
    fake = FakeCoordinator()

    fake.hybrid_response = SearchResponse(
        results=[
            SearchResult(
                doc_id=100,
                score=0.97,
            ),
            SearchResult(
                doc_id=200,
                score=0.88,
            ),
        ],
        total_shards=4,
        successful_shards=4,
        failed_shards=0,
        timed_out_shards=0,
    )

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "distributed systems",
            "mode": "hybrid",
            "limit": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "query": "distributed systems",
        "mode": "hybrid",
        "results": [
            {
                "doc_id": 100,
                "score": 0.97,
            },
            {
                "doc_id": 200,
                "score": 0.88,
            },
        ],
        "total_shards": 4,
        "successful_shards": 4,
        "failed_shards": 0,
        "timed_out_shards": 0,
        "partial": False,
    }


def test_search_endpoint_exposes_failed_shard_as_partial():
    fake = FakeCoordinator()

    fake.hybrid_response = SearchResponse(
        results=[
            SearchResult(
                doc_id=101,
                score=0.91,
            ),
        ],
        total_shards=3,
        successful_shards=2,
        failed_shards=1,
        timed_out_shards=0,
    )

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "distributed search",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["results"] == [
        {
            "doc_id": 101,
            "score": 0.91,
        },
    ]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 2
    assert body["failed_shards"] == 1
    assert body["timed_out_shards"] == 0
    assert body["partial"] is True


def test_search_endpoint_exposes_timeout_as_partial():
    fake = FakeCoordinator()

    fake.hybrid_response = SearchResponse(
        results=[
            SearchResult(
                doc_id=102,
                score=0.84,
            ),
        ],
        total_shards=3,
        successful_shards=2,
        failed_shards=0,
        timed_out_shards=1,
    )

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "distributed search",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["results"] == [
        {
            "doc_id": 102,
            "score": 0.84,
        },
    ]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 2
    assert body["failed_shards"] == 0
    assert body["timed_out_shards"] == 1
    assert body["partial"] is True


def test_search_endpoint_exposes_failed_and_timed_out_shards():
    fake = FakeCoordinator()

    fake.hybrid_response = SearchResponse(
        results=[
            SearchResult(
                doc_id=103,
                score=0.79,
            ),
        ],
        total_shards=4,
        successful_shards=2,
        failed_shards=1,
        timed_out_shards=1,
    )

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "distributed search",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total_shards"] == 4
    assert body["successful_shards"] == 2
    assert body["failed_shards"] == 1
    assert body["timed_out_shards"] == 1
    assert body["partial"] is True

    assert body["results"] == [
        {
            "doc_id": 103,
            "score": 0.79,
        },
    ]


def test_partial_response_preserves_query_and_mode():
    fake = FakeCoordinator()

    fake.semantic_response = SearchResponse(
        results=[
            SearchResult(
                doc_id=500,
                score=0.76,
            ),
        ],
        total_shards=5,
        successful_shards=4,
        failed_shards=1,
        timed_out_shards=0,
    )

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "vector databases",
            "mode": "semantic",
            "limit": 8,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "vector databases"
    assert body["mode"] == "semantic"
    assert body["partial"] is True

    assert body["successful_shards"] == 4
    assert body["failed_shards"] == 1
    assert body["timed_out_shards"] == 0

    assert fake.calls == [
        (
            "semantic",
            "vector databases",
            8,
        ),
    ]


def test_search_endpoint_rejects_empty_query():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "   ",
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Query must not be empty."
    )

    assert fake.calls == []


def test_search_endpoint_rejects_missing_query():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get("/search")

    assert response.status_code == 422


def test_search_endpoint_rejects_invalid_mode():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "search",
            "mode": "invalid",
        },
    )

    assert response.status_code == 422


def test_search_endpoint_rejects_invalid_limit():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "search",
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_search_endpoint_rejects_limit_above_maximum():
    fake = FakeCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "search",
            "limit": 101,
        },
    )

    assert response.status_code == 422


def test_search_endpoint_returns_503_for_coordinator_runtime_error():
    class FailingCoordinator(FakeCoordinator):
        def hybrid_search(
            self,
            query: str,
            limit: int,
        ) -> SearchResponse:
            raise RuntimeError(
                "Search failed because one or more shards "
                "were unavailable."
            )

    fake = FailingCoordinator()

    client = _client_with_fake_coordinator(fake)

    response = client.get(
        "/search",
        params={
            "q": "distributed search",
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "Search failed because one or more shards "
        "were unavailable."
    )