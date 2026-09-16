import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.models import Document
from services.events.consumer import DocumentEventConsumer
from services.indexer.analyzer import TextAnalyzer
from services.indexer.index import InvertedIndex
from services.indexer.remote_shard_client import HttpShardIndexClient
from services.indexer.shard import Shard
from services.indexer.shard_manager import ShardManager
from services.indexer.worker import IndexerWorker
from services.semantic.embedding import EmbeddingModel
from services.semantic.models import Embedding
from services.shard.main import create_app


def test_shard_manager_stores_lexical_and_semantic_representations_together():
    manager = ShardManager(
        ["shard-0", "shard-1"]
    )

    embedding = Embedding(
        [1.0, 0.0, 0.0]
    )

    shard_id = manager.index_document(
        document_id=42,
        tokens=["distribut", "search"],
        embedding=embedding,
    )

    shard = manager.get_shard(
        shard_id
    )

    assert shard.contains_document(42)
    assert shard.vector_index.contains_document(42)
    assert shard.vector_index.get_embedding(42) == embedding


def test_removing_document_removes_vector_representation_too():
    manager = ShardManager(
        ["shard-0"]
    )

    manager.index_document(
        document_id=42,
        tokens=["search"],
        embedding=Embedding(
            [1.0, 0.0]
        ),
    )

    manager.remove_document(
        42
    )

    shard = manager.get_shard(
        "shard-0"
    )

    assert not shard.contains_document(42)
    assert not shard.vector_index.contains_document(42)


def test_worker_generates_embedding_before_local_indexing():
    db = Mock(
        spec=Session
    )

    shard_manager = Mock(
        spec=ShardManager
    )

    consumer = Mock(
        spec=DocumentEventConsumer
    )

    analyzer = Mock(
        spec=TextAnalyzer
    )

    embedding_model = Mock(
        spec=EmbeddingModel
    )

    document = Document(
        id=42,
        url="https://example.com/test",
        title="Test",
        content="Distributed search with Python",
        content_type="text/html",
        content_hash="hash-v1",
        version=1,
    )

    db.get.return_value = document

    analyzer.analyze.return_value = [
        "distribut",
        "search",
        "python",
    ]

    embedding = Embedding(
        [0.1, 0.2, 0.3]
    )

    embedding_model.embed.return_value = (
        embedding
    )

    worker = IndexerWorker(
        db=db,
        shard_manager=shard_manager,
        consumer=consumer,
        analyzer=analyzer,
        embedding_model=embedding_model,
    )

    event = DocumentChangeEvent.create(
        event_type=DocumentEventType.CREATED,
        document_id=42,
        url=document.url,
        content_hash=document.content_hash,
        event_version=document.version,
        occurred_at=datetime(
            2026,
            9,
            15,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )

    worker.process_event(
        event
    )

    analyzer.analyze.assert_called_once_with(
        f"{document.title}\n{document.content}"
    )

    embedding_model.embed.assert_called_once_with(
        document.content
    )

    shard_manager.index_document.assert_called_once_with(
        document_id=42,
        tokens=[
            "distribut",
            "search",
            "python",
        ],
        embedding=embedding,
    )


def test_remote_shard_client_sends_embedding_in_index_request():
    client = HttpShardIndexClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8101",
    )

    response = Mock()
    response.status = 200
    response.read.return_value = b"{}"
    response.__enter__ = Mock(
        return_value=response
    )
    response.__exit__ = Mock(
        return_value=False
    )

    with patch(
        "services.indexer.remote_shard_client.urlopen",
        return_value=response,
    ) as urlopen:
        client.index_document(
            document_id=42,
            tokens=["search"],
            embedding=Embedding(
                [0.25, 0.75]
            ),
        )

    request = urlopen.call_args.args[0]

    payload = json.loads(
        request.data.decode("utf-8")
    )

    assert payload == {
        "document_id": 42,
        "tokens": ["search"],
        "embedding": [
            0.25,
            0.75,
        ],
    }


def test_shard_http_endpoint_stores_embedding_in_same_shard():
    shard = Shard(
        shard_id="test-shard",
        index=InvertedIndex(),
    )

    client = TestClient(
        create_app(shard)
    )

    response = client.post(
        "/documents",
        json={
            "document_id": 77,
            "tokens": [
                "semantic",
                "search",
            ],
            "embedding": [
                0.4,
                0.6,
            ],
        },
    )

    assert response.status_code == 200

    assert shard.contains_document(
        77
    )

    assert shard.vector_index.get_embedding(
        77
    ) == Embedding(
        [0.4, 0.6]
    )