from fastapi.testclient import TestClient

from services.shard.config import ShardServiceConfig
from services.shard.main import create_app, create_service


def test_service_loads_persisted_shard_after_restart(
    tmp_path,
):
    config = ShardServiceConfig(
        shard_id="shard-restart",
        host="127.0.0.1",
        port=8001,
        data_path=str(tmp_path),
    )

    first_service = create_service(
        config
    )

    first_client = TestClient(
        create_app(first_service)
    )

    response = first_client.post(
        "/documents",
        json={
            "document_id": 5001,
            "tokens": [
                "python",
                "distributed",
                "search",
            ],
        },
    )

    assert response.status_code == 200

    first_client.close()

    second_service = create_service(
        config
    )

    second_client = TestClient(
        create_app(second_service)
    )

    response = second_client.get(
        "/search",
        params={
            "q": "python",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    document_ids = [
        result["doc_id"]
        for result in body["results"]
    ]

    assert 5001 in document_ids

    assert (
        second_service.document_count == 1
    )

    second_client.close()


def test_service_persists_delete(
    tmp_path,
):
    config = ShardServiceConfig(
        shard_id="shard-delete",
        host="127.0.0.1",
        port=8002,
        data_path=str(tmp_path),
    )

    first_service = create_service(
        config
    )

    first_client = TestClient(
        create_app(first_service)
    )

    response = first_client.post(
        "/documents",
        json={
            "document_id": 6001,
            "tokens": [
                "distributed",
                "search",
            ],
        },
    )

    assert response.status_code == 200

    response = first_client.delete(
        "/documents/6001"
    )

    assert response.status_code == 200

    first_client.close()

    second_service = create_service(
        config
    )

    assert not second_service.contains_document(
        6001
    )

    second_client = TestClient(
        create_app(second_service)
    )

    response = second_client.get(
        "/search",
        params={
            "q": "distributed",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    document_ids = [
        result["doc_id"]
        for result in body["results"]
    ]

    assert 6001 not in document_ids

    second_client.close()


def test_missing_persistent_shard_starts_new(
    tmp_path,
):
    config = ShardServiceConfig(
        shard_id="new-shard",
        host="127.0.0.1",
        port=8003,
        data_path=str(tmp_path),
    )

    service = create_service(
        config
    )

    assert service.document_count == 0

    assert service.lifecycle_state.value == "new"