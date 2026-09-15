from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.indexer.shard_manager import ShardManager
from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import HttpShardSearchClient
from services.semantic.models import Embedding
from services.shard.main import create_app


class FakeEmbeddingModel:
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> Embedding:
        self.calls.append(text)

        if text == "python search":
            return Embedding(
                [1.0, 0.0, 0.0]
            )

        return Embedding(
            [0.0, 1.0, 0.0]
        )


def make_shard(
    shard_id: str,
) -> Shard:
    return Shard(
        shard_id=shard_id,
        index=InvertedIndex(),
    )


def test_local_coordinator_searches_semantic_index_across_all_shards():
    manager = ShardManager(
        ["shard-1", "shard-2"],
    )

    manager.index_document(
        document_id=1,
        tokens=["python"],
        embedding=Embedding(
            [1.0, 0.0, 0.0]
        ),
    )

    manager.index_document(
        document_id=2,
        tokens=["javascript"],
        embedding=Embedding(
            [0.0, 1.0, 0.0]
        ),
    )

    model = FakeEmbeddingModel()

    coordinator = SearchCoordinator(
        manager,
        embedding_model=model,
    )

    response = coordinator.semantic_search(
        "python search",
        limit=2,
    )

    assert [
        result.doc_id
        for result in response.results
    ] == [1, 2]

    assert response.total_shards == 2
    assert response.successful_shards == 2
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0
    assert response.is_partial is False

    assert model.calls == [
        "python search"
    ]


def test_semantic_search_requires_embedding_model():
    coordinator = SearchCoordinator(
        ShardManager(
            ["shard-1"]
        ),
    )

    try:
        coordinator.semantic_search(
            "python"
        )
    except RuntimeError as exc:
        assert "embedding_model" in str(exc)
    else:
        raise AssertionError(
            "Expected missing embedding model failure"
        )


def test_shard_semantic_endpoint_returns_vector_results():
    shard = make_shard(
        "shard-1"
    )

    shard.add_document(
        doc_id=1,
        tokens=["python"],
        embedding=Embedding(
            [1.0, 0.0, 0.0]
        ),
    )

    shard.add_document(
        doc_id=2,
        tokens=["javascript"],
        embedding=Embedding(
            [0.0, 1.0, 0.0]
        ),
    )

    client = TestClient(
        create_app(shard)
    )

    response = client.post(
        "/semantic-search?limit=2",
        json={
            "embedding": [
                1.0,
                0.0,
                0.0,
            ]
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["shard_id"] == "shard-1"

    assert [
        result["doc_id"]
        for result in payload["results"]
    ] == [1, 2]


def test_remote_semantic_client_sends_embedding():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            return False

        def read(self):
            return json.dumps(
                {
                    "shard_id": "shard-1",
                    "results": [
                        {
                            "doc_id": 10,
                            "score": 0.95,
                        }
                    ],
                }
            ).encode("utf-8")

    with patch(
        "services.search.http_shard_client.urlopen",
        return_value=FakeResponse(),
    ) as mock_urlopen:
        results = client.semantic_search(
            Embedding(
                [1.0, 0.0, 0.0]
            ),
            limit=5,
        )

    assert results[0].doc_id == 10
    assert results[0].score == 0.95

    request = mock_urlopen.call_args.args[0]

    assert request.full_url == (
        "http://127.0.0.1:8001/"
        "semantic-search?limit=5"
    )

    assert json.loads(
        request.data.decode("utf-8")
    ) == {
        "embedding": [
            1.0,
            0.0,
            0.0,
        ]
    }


def test_semantic_search_partial_failure_preserves_existing_failure_semantics():
    manager = ShardManager(
        ["shard-1", "shard-2"],
    )

    manager.index_document(
        document_id=1,
        tokens=["python"],
        embedding=Embedding(
            [1.0, 0.0, 0.0]
        ),
    )

    failing_shard = manager.get_shard(
        "shard-1"
    )

    original = (
        failing_shard.semantic_search
    )

    def fail(
        query_embedding,
        limit,
    ):
        raise RuntimeError(
            "Shard unavailable"
        )

    failing_shard.semantic_search = fail

    try:
        coordinator = SearchCoordinator(
            manager,
            embedding_model=FakeEmbeddingModel(),
            allow_partial_results=True,
        )

        response = coordinator.semantic_search(
            "python"
        )

        assert response.failed_shards == 1
        assert response.successful_shards == 1
        assert response.is_partial is True

    finally:
        failing_shard.semantic_search = original