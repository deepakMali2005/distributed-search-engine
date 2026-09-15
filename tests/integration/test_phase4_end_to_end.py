from __future__ import annotations

from fastapi.testclient import TestClient

from services.search_api import main


def test_phase4_search_api_supports_all_retrieval_modes():
    """
    Final API contract smoke test.

    The underlying distributed HTTP integration is already verified in
    test_search_api_http.py. This test verifies that the public API exposes
    all three retrieval modes consistently.
    """

    class FakeCoordinator:
        def __init__(self):
            self.calls = []

        def search(self, query, limit):
            self.calls.append(("lexical", query, limit))

            return _response(
                doc_ids=[101, 102],
                total_shards=3,
                successful_shards=3,
            )

        def semantic_search(self, query, limit):
            self.calls.append(("semantic", query, limit))

            return _response(
                doc_ids=[201, 202],
                total_shards=3,
                successful_shards=3,
            )

        def hybrid_search(self, query, limit):
            self.calls.append(("hybrid", query, limit))

            return _response(
                doc_ids=[301, 302],
                total_shards=3,
                successful_shards=3,
            )

    coordinator = FakeCoordinator()
    main.search_coordinator = coordinator

    client = TestClient(main.app)

    lexical = client.get(
        "/search",
        params={
            "q": "python",
            "mode": "lexical",
        },
    )

    semantic = client.get(
        "/search",
        params={
            "q": "python programming",
            "mode": "semantic",
        },
    )

    hybrid = client.get(
        "/search",
        params={
            "q": "distributed search",
            "mode": "hybrid",
        },
    )

    assert lexical.status_code == 200
    assert semantic.status_code == 200
    assert hybrid.status_code == 200

    assert lexical.json()["mode"] == "lexical"
    assert semantic.json()["mode"] == "semantic"
    assert hybrid.json()["mode"] == "hybrid"

    assert coordinator.calls == [
        ("lexical", "python", 10),
        ("semantic", "python programming", 10),
        ("hybrid", "distributed search", 10),
    ]


def test_phase4_api_exposes_complete_distributed_result():
    """
    A fully healthy distributed cluster must be represented as a complete
    response at the public API boundary.
    """

    class HealthyCoordinator:
        def hybrid_search(self, query, limit):
            return _response(
                doc_ids=[1001, 1002, 1003],
                total_shards=3,
                successful_shards=3,
            )

    main.search_coordinator = HealthyCoordinator()

    client = TestClient(main.app)

    response = client.get(
        "/search",
        params={
            "q": "distributed systems",
            "mode": "hybrid",
            "limit": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "distributed systems"
    assert body["mode"] == "hybrid"

    assert [item["doc_id"] for item in body["results"]] == [
        1001,
        1002,
        1003,
    ]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 3
    assert body["failed_shards"] == 0
    assert body["timed_out_shards"] == 0
    assert body["partial"] is False


def test_phase4_api_exposes_partial_distributed_result():
    """
    If a shard is unavailable but partial results are allowed, the API must
    preserve the useful results and explicitly mark the response partial.
    """

    class PartiallyAvailableCoordinator:
        def hybrid_search(self, query, limit):
            return _response(
                doc_ids=[2001, 2002],
                total_shards=3,
                successful_shards=2,
                failed_shards=1,
            )

    main.search_coordinator = PartiallyAvailableCoordinator()

    client = TestClient(main.app)

    response = client.get(
        "/search",
        params={
            "q": "fault tolerant search",
            "mode": "hybrid",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["results"]

    assert body["total_shards"] == 3
    assert body["successful_shards"] == 2
    assert body["failed_shards"] == 1
    assert body["timed_out_shards"] == 0

    assert body["partial"] is True


def test_phase4_api_exposes_timeout_and_failure_metadata():
    """
    Timeout and hard failure are distinct distributed outcomes and both
    must survive the API boundary.
    """

    class DegradedCoordinator:
        def hybrid_search(self, query, limit):
            return _response(
                doc_ids=[3001],
                total_shards=4,
                successful_shards=2,
                failed_shards=1,
                timed_out_shards=1,
            )

    main.search_coordinator = DegradedCoordinator()

    client = TestClient(main.app)

    response = client.get(
        "/search",
        params={
            "q": "distributed failure recovery",
            "mode": "hybrid",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total_shards"] == 4
    assert body["successful_shards"] == 2
    assert body["failed_shards"] == 1
    assert body["timed_out_shards"] == 1
    assert body["partial"] is True


def _response(
    *,
    doc_ids,
    total_shards,
    successful_shards,
    failed_shards=0,
    timed_out_shards=0,
):
    from services.search.coordinator import SearchResponse
    from services.search.models import SearchResult

    return SearchResponse(
        results=[
            SearchResult(
                doc_id=doc_id,
                score=1.0 / index,
            )
            for index, doc_id in enumerate(
                doc_ids,
                start=1,
            )
        ],
        total_shards=total_shards,
        successful_shards=successful_shards,
        failed_shards=failed_shards,
        timed_out_shards=timed_out_shards,
    )