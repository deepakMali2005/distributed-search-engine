from __future__ import annotations

from fastapi.testclient import TestClient

from services.search.coordinator import SearchResponse
from services.search.models import SearchResult
from services.search_api import main


class FakeCoordinator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def search(
        self,
        query: str,
        limit: int,
    ) -> SearchResponse:
        self.calls.append(("lexical", query, limit))

        return SearchResponse(
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

    def semantic_search(
        self,
        query: str,
        limit: int,
    ) -> SearchResponse:
        self.calls.append(("semantic", query, limit))

        return SearchResponse(
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

    def hybrid_search(
        self,
        query: str,
        limit: int,
    ) -> SearchResponse:
        self.calls.append(("hybrid", query, limit))

        return SearchResponse(
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
        ("hybrid", "distributed search", 10),
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

    assert fake.calls == [
        ("lexical", "python", 5),
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

    assert body["mode"] == "semantic"
    assert body["results"] == [
        {
            "doc_id": 3,
            "score": 0.95,
        },
    ]

    assert fake.calls == [
        ("semantic", "machine learning", 3),
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
    assert response.json()["detail"] == "Query must not be empty."


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