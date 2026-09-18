from fastapi.testclient import TestClient

from services.shard.config import ShardServiceConfig
from services.shard.main import create_app, create_service


def test_bulk_index_persists_all_documents(
    tmp_path,
):
    config = ShardServiceConfig(
        shard_id="bulk-test",
        host="127.0.0.1",
        port=8010,
        data_path=str(tmp_path),
    )

    service = create_service(
        config
    )

    client = TestClient(
        create_app(service)
    )

    response = client.post(
        "/documents/bulk",
        json={
            "documents": [
                {
                    "document_id": 1001,
                    "tokens": [
                        "distributed",
                        "search",
                    ],
                },
                {
                    "document_id": 1002,
                    "tokens": [
                        "semantic",
                        "search",
                    ],
                },
                {
                    "document_id": 1003,
                    "tokens": [
                        "hybrid",
                        "search",
                    ],
                },
            ]
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "shard_id": "bulk-test",
        "document_count": 3,
    }

    assert service.document_count == 3

    assert service.contains_document(
        1001
    )

    assert service.contains_document(
        1002
    )

    assert service.contains_document(
        1003
    )

    client.close()


def test_bulk_index_rejects_duplicate_document_ids(
    tmp_path,
):
    config = ShardServiceConfig(
        shard_id="bulk-duplicate-test",
        host="127.0.0.1",
        port=8011,
        data_path=str(tmp_path),
    )

    service = create_service(
        config
    )

    client = TestClient(
        create_app(service)
    )

    response = client.post(
        "/documents/bulk",
        json={
            "documents": [
                {
                    "document_id": 2001,
                    "tokens": ["search"],
                },
                {
                    "document_id": 2001,
                    "tokens": ["distributed"],
                },
            ]
        },
    )

    assert response.status_code == 400

    assert service.document_count == 0

    client.close()


def test_bulk_index_survives_service_restart(
    tmp_path,
):
    config = ShardServiceConfig(
        shard_id="bulk-restart-test",
        host="127.0.0.1",
        port=8012,
        data_path=str(tmp_path),
    )

    first_service = create_service(
        config
    )

    first_client = TestClient(
        create_app(first_service)
    )

    response = first_client.post(
        "/documents/bulk",
        json={
            "documents": [
                {
                    "document_id": 3001,
                    "tokens": [
                        "distributed",
                        "search",
                    ],
                },
                {
                    "document_id": 3002,
                    "tokens": [
                        "semantic",
                        "search",
                    ],
                },
            ]
        },
    )

    assert response.status_code == 200

    first_client.close()

    second_service = create_service(
        config
    )

    assert second_service.document_count == 2

    assert second_service.contains_document(
        3001
    )

    assert second_service.contains_document(
        3002
    )