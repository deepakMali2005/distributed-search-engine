from fastapi.testclient import TestClient

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.shard.main import create_app


def create_test_client() -> TestClient:
    shard = Shard(
        shard_id="test-shard",
        index=InvertedIndex(),
    )

    return TestClient(
        create_app(shard)
    )


def test_health():
    client = create_test_client()

    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ok"
    assert body["shard_id"] == "test-shard"


def test_index_document():
    client = create_test_client()

    response = client.post(
        "/documents",
        json={
            "document_id": 1001,
            "tokens": [
                "distribut",
                "search",
                "engin",
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["shard_id"] == "test-shard"
    assert body["document_id"] == 1001


def test_search_document():
    client = create_test_client()

    response = client.post(
        "/documents",
        json={
            "document_id": 1002,
            "tokens": [
                "python",
                "search",
                "engin",
            ],
        },
    )

    assert response.status_code == 200

    response = client.get(
        "/search",
        params={
            "q": "python",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["shard_id"] == "test-shard"

    document_ids = [
        result["doc_id"]
        for result in body["results"]
    ]

    assert 1002 in document_ids


def test_delete_document():
    client = create_test_client()

    response = client.post(
        "/documents",
        json={
            "document_id": 1003,
            "tokens": [
                "distribut",
                "search",
            ],
        },
    )

    assert response.status_code == 200

    response = client.delete(
        "/documents/1003",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["shard_id"] == "test-shard"
    assert body["document_id"] == 1003


def test_delete_missing_document_returns_404():
    client = create_test_client()

    response = client.delete(
        "/documents/999999",
    )

    assert response.status_code == 404


def test_search_requires_query():
    client = create_test_client()

    response = client.get("/search")

    assert response.status_code == 422