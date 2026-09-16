from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.models import Document
from services.events.consumer import DocumentEventConsumer
from services.events.producer import DocumentEventProducer
from services.indexer.analyzer import TextAnalyzer
from services.indexer.shard_manager import ShardManager
from services.indexer.worker import IndexerWorker


def make_event(
    *,
    event_type: DocumentEventType = DocumentEventType.CREATED,
    version: int = 1,
    content_hash: str | None = "hash-v1",
) -> DocumentChangeEvent:
    return DocumentChangeEvent.create(
        event_type=event_type,
        document_id=42,
        url="https://example.com/test",
        content_hash=content_hash,
        event_version=version,
        occurred_at=datetime(
            2026,
            9,
            13,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )


def make_document(
    *,
    version: int = 1,
    content_hash: str = "hash-v1",
) -> Document:
    return Document(
        id=42,
        url="https://example.com/test",
        title="Test",
        content="Distributed search with Python",
        content_type="text/html",
        content_hash=content_hash,
        version=version,
    )


def make_worker():
    db = Mock(spec=Session)
    shard_manager = Mock(spec=ShardManager)
    consumer = Mock(spec=DocumentEventConsumer)
    analyzer = Mock(spec=TextAnalyzer)

    worker = IndexerWorker(
        db=db,
        shard_manager=shard_manager,
        consumer=consumer,
        analyzer=analyzer,
    )

    return (
        worker,
        db,
        shard_manager,
        consumer,
        analyzer,
    )


def make_message(
    event: DocumentChangeEvent,
):
    message = Mock()
    message.error.return_value = None
    message.value.return_value = (
        event.to_json().encode("utf-8")
    )
    return message


def test_created_event_fetches_analyzes_and_indexes_document():
    worker, db, shard_manager, _, analyzer = make_worker()

    document = make_document()

    db.get.return_value = document

    analyzer.analyze.return_value = [
        "distribut",
        "search",
        "python",
    ]

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ), patch(
        "services.indexer.worker.record_processed_event"
    ) as record_event:
        worker.process_event(
            make_event()
        )

        db.get.assert_called_once_with(
            Document,
            42,
        )

        analyzer.analyze.assert_called_once_with(
            f"{document.title}\n{document.content}"
        )

        shard_manager.index_document.assert_called_once_with(
            document_id=42,
            tokens=[
                "distribut",
                "search",
                "python",
            ],
            embedding=None,
        )

        record_event.assert_not_called()


def test_deleted_event_removes_document_without_database_fetch():
    worker, db, shard_manager, _, analyzer = make_worker()

    event = make_event(
        event_type=DocumentEventType.DELETED,
        content_hash=None,
    )

    worker.process_event(
        event
    )

    shard_manager.remove_document.assert_called_once_with(
        42
    )

    db.get.assert_not_called()
    analyzer.analyze.assert_not_called()
    shard_manager.index_document.assert_not_called()


def test_missing_document_is_rejected():
    worker, db, shard_manager, _, analyzer = make_worker()

    db.get.return_value = None

    with pytest.raises(
        RuntimeError,
        match="does not exist",
    ):
        worker.process_event(
            make_event()
        )

    analyzer.analyze.assert_not_called()
    shard_manager.index_document.assert_not_called()


def test_document_version_mismatch_is_treated_as_stale():
    worker, db, shard_manager, _, analyzer = make_worker()

    db.get.return_value = make_document(
        version=2
    )

    event = make_event(
        version=1
    )

    applied = worker.process_event(event)

    assert applied is False
    shard_manager.index_document.assert_not_called()
    analyzer.analyze.assert_not_called()


def test_document_content_hash_mismatch_is_rejected():
    worker, db, shard_manager, _, analyzer = make_worker()

    db.get.return_value = make_document(
        content_hash="different-hash"
    )

    with pytest.raises(
        RuntimeError,
        match="content hash mismatch",
    ):
        worker.process_event(
            make_event()
        )

    analyzer.analyze.assert_not_called()
    shard_manager.index_document.assert_not_called()


def test_successful_message_is_processed_recorded_and_committed():
    worker, db, shard_manager, consumer, analyzer = make_worker()

    db.get.return_value = make_document()

    analyzer.analyze.return_value = [
        "search"
    ]

    event = make_event()
    message = make_message(event)

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ) as is_processed, patch(
        "services.indexer.worker.record_processed_event"
    ) as record_event:
        worker.process_message(
            message
        )

        is_processed.assert_called_once_with(
            db=db,
            event_id=event.event_id,
        )

        record_event.assert_called_once_with(
            db=db,
            event=event,
        )

    shard_manager.index_document.assert_called_once()
    consumer.commit.assert_called_once_with(
        message
    )


def test_duplicate_message_is_not_processed_again():
    worker, db, shard_manager, consumer, analyzer = make_worker()

    event = make_event()
    message = make_message(event)

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=True,
    ), patch(
        "services.indexer.worker.record_processed_event"
    ) as record_event:
        worker.process_message(
            message
        )

    shard_manager.index_document.assert_not_called()
    shard_manager.remove_document.assert_not_called()
    analyzer.analyze.assert_not_called()

    record_event.assert_not_called()

    consumer.commit.assert_called_once_with(
        message
    )


def test_failed_message_is_not_recorded_or_committed():
    worker, db, shard_manager, consumer, analyzer = make_worker()

    db.get.return_value = None

    message = make_message(
        make_event()
    )

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ), patch(
        "services.indexer.worker.record_processed_event"
    ) as record_event:
        with pytest.raises(RuntimeError):
            worker.process_message(
                message
            )

    record_event.assert_not_called()
    consumer.commit.assert_not_called()

    shard_manager.index_document.assert_not_called()
    analyzer.analyze.assert_not_called()


def test_kafka_message_error_is_rejected_without_commit():
    worker, _, _, consumer, _ = make_worker()

    message = Mock()
    message.error.return_value = "broker failure"

    with pytest.raises(
        RuntimeError,
        match="Kafka consumer error",
    ):
        worker.process_message(
            message
        )

    consumer.commit.assert_not_called()


def test_missing_message_payload_is_rejected_without_commit():
    worker, _, _, consumer, _ = make_worker()

    message = Mock()
    message.error.return_value = None
    message.value.return_value = None

    with pytest.raises(
        ValueError,
        match="no payload",
    ):
        worker.process_message(
            message
        )

    consumer.commit.assert_not_called()


def test_run_once_returns_false_when_no_message_is_available():
    worker, _, _, consumer, _ = make_worker()

    consumer.poll.return_value = None

    processed = worker.run_once(
        timeout=2.0
    )

    assert processed is False

    consumer.poll.assert_called_once_with(
        2.0
    )

    consumer.commit.assert_not_called()


def test_run_once_processes_one_message():
    worker, db, _, consumer, analyzer = make_worker()

    db.get.return_value = make_document()

    analyzer.analyze.return_value = [
        "search"
    ]

    message = make_message(
        make_event()
    )

    consumer.poll.return_value = message

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ), patch(
        "services.indexer.worker.record_processed_event"
    ):
        processed = worker.run_once(
            timeout=2.0
        )

    assert processed is True

    consumer.poll.assert_called_once_with(
        2.0
    )

    consumer.commit.assert_called_once_with(
        message
    )


def test_already_processed_message_is_committed_without_indexing():
    worker, _, shard_manager, consumer, analyzer = make_worker()

    event = make_event()
    message = make_message(event)

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=True,
    ):
        worker.process_message(
            message
        )

    consumer.commit.assert_called_once_with(
        message
    )

    shard_manager.index_document.assert_not_called()
    shard_manager.remove_document.assert_not_called()
    analyzer.analyze.assert_not_called()


def test_event_is_recorded_only_after_successful_processing():
    worker, db, shard_manager, consumer, analyzer = make_worker()

    db.get.return_value = make_document()

    analyzer.analyze.return_value = [
        "search"
    ]

    event = make_event()
    message = make_message(event)

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ), patch(
        "services.indexer.worker.record_processed_event"
    ) as record_event:
        worker.process_message(
            message
        )

        record_event.assert_called_once_with(
            db=db,
            event=event,
        )

    shard_manager.index_document.assert_called_once()
    consumer.commit.assert_called_once_with(
        message
    )


def test_recording_failure_prevents_kafka_commit():
    worker, db, _, consumer, analyzer = make_worker()

    db.get.return_value = make_document()

    analyzer.analyze.return_value = [
        "search"
    ]

    event = make_event()
    message = make_message(event)

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ), patch(
        "services.indexer.worker.record_processed_event",
        side_effect=RuntimeError(
            "database unavailable"
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="database unavailable",
        ):
            worker.process_message(
                message
            )

    consumer.commit.assert_not_called()


def test_exhausted_retries_publish_to_dlq_then_commit():
    worker, db, shard_manager, consumer, analyzer = make_worker()

    dlq_producer = Mock(
        spec=DocumentEventProducer
    )

    worker.dlq_producer = dlq_producer
    worker.max_retries = 2
    worker.retry_delay = 0

    db.get.return_value = None

    event = make_event()
    message = make_message(event)

    worker.process_message_with_retry(
        message
    )

    dlq_producer.publish_to_dlq.assert_called_once_with(
        event
    )

    consumer.commit.assert_called_once_with(
        message
    )

    analyzer.analyze.assert_not_called()
    shard_manager.index_document.assert_not_called()


def test_dlq_publish_failure_does_not_commit():
    worker, db, _, consumer, _ = make_worker()

    dlq_producer = Mock(
        spec=DocumentEventProducer
    )

    dlq_producer.publish_to_dlq.side_effect = RuntimeError(
        "dlq unavailable"
    )

    worker.dlq_producer = dlq_producer
    worker.max_retries = 0
    worker.retry_delay = 0

    db.get.return_value = None

    message = make_message(
        make_event()
    )

    with pytest.raises(
        RuntimeError,
        match="dlq unavailable",
    ):
        worker.process_message_with_retry(
            message
        )

    consumer.commit.assert_not_called()


def test_retry_succeeds_before_dlq():
    worker, _, _, consumer, _ = make_worker()

    worker.max_retries = 2
    worker.retry_delay = 0

    message = make_message(
        make_event()
    )

    calls = {
        "count": 0
    }

    def process_once(
        _message,
    ):
        calls["count"] += 1

        if calls["count"] < 2:
            raise RuntimeError(
                "temporary failure"
            )

    worker.process_message = process_once

    worker.process_message_with_retry(
        message
    )

    assert calls["count"] == 2

    consumer.commit.assert_not_called()


def test_exhausted_retries_attempt_original_plus_max_retries():
    worker, _, _, consumer, _ = make_worker()

    dlq_producer = Mock(
        spec=DocumentEventProducer
    )

    worker.dlq_producer = dlq_producer
    worker.max_retries = 3
    worker.retry_delay = 0

    message = make_message(
        make_event()
    )

    calls = {
        "count": 0
    }

    def process_once(
        _message,
    ):
        calls["count"] += 1

        raise RuntimeError(
            "permanent failure"
        )

    worker.process_message = process_once

    worker.process_message_with_retry(
        message
    )

    assert calls["count"] == 4

    dlq_producer.publish_to_dlq.assert_called_once()

    consumer.commit.assert_called_once_with(
        message
    )


def test_worker_rejects_negative_max_retries():
    db = Mock(spec=Session)
    shard_manager = Mock(spec=ShardManager)
    consumer = Mock(spec=DocumentEventConsumer)

    with pytest.raises(
        ValueError,
        match="max_retries",
    ):
        IndexerWorker(
            db=db,
            shard_manager=shard_manager,
            consumer=consumer,
            max_retries=-1,
        )


def test_worker_rejects_negative_retry_delay():
    db = Mock(spec=Session)
    shard_manager = Mock(spec=ShardManager)
    consumer = Mock(spec=DocumentEventConsumer)

    with pytest.raises(
        ValueError,
        match="retry_delay",
    ):
        IndexerWorker(
            db=db,
            shard_manager=shard_manager,
            consumer=consumer,
            retry_delay=-1,
        )


def test_stale_event_is_ignored_when_newer_index_version_exists(
    monkeypatch,
):
    worker, db, shard_manager, consumer, analyzer = make_worker()

    event = make_event(version=1)
    message = make_message(event)

    monkeypatch.setattr(
        "services.indexer.worker.is_event_processed",
        lambda db, event_id: False,
    )

    monkeypatch.setattr(
        "services.indexer.worker.get_latest_indexed_version",
        lambda db, document_id: 2,
    )

    record_processed = Mock()

    monkeypatch.setattr(
        "services.indexer.worker.record_processed_event",
        record_processed,
    )

    worker.process_message(message)

    shard_manager.index_document.assert_not_called()
    shard_manager.remove_document.assert_not_called()
    analyzer.analyze.assert_not_called()

    record_processed.assert_called_once_with(
        db=db,
        event=event,
    )

    consumer.commit.assert_called_once_with(message)


def test_stale_event_is_ignored_when_database_has_newer_version(
    monkeypatch,
):
    worker, db, shard_manager, consumer, analyzer = make_worker()

    event = make_event(version=1)
    message = make_message(event)

    db.get.return_value = make_document(version=2)

    monkeypatch.setattr(
        "services.indexer.worker.is_event_processed",
        lambda db, event_id: False,
    )

    monkeypatch.setattr(
        "services.indexer.worker.get_latest_indexed_version",
        lambda db, document_id: None,
    )

    record_processed = Mock()

    monkeypatch.setattr(
        "services.indexer.worker.record_processed_event",
        record_processed,
    )

    worker.process_message(message)

    shard_manager.index_document.assert_not_called()
    analyzer.analyze.assert_not_called()

    record_processed.assert_called_once_with(
        db=db,
        event=event,
    )

    consumer.commit.assert_called_once_with(message)


def test_future_event_is_rejected_when_database_is_behind():
    worker, db, shard_manager, _, analyzer = make_worker()

    db.get.return_value = make_document(version=1)

    event = make_event(version=2)

    with pytest.raises(RuntimeError, match="version mismatch"):
        worker.process_event(event)

    shard_manager.index_document.assert_not_called()
    analyzer.analyze.assert_not_called()


def test_current_version_is_indexed_and_version_is_recorded(
    monkeypatch,
):
    worker, db, shard_manager, consumer, analyzer = make_worker()

    document = make_document(version=2)

    db.get.return_value = document

    event = make_event(version=2)
    message = make_message(event)

    analyzer.analyze.return_value = ["search"]

    monkeypatch.setattr(
        "services.indexer.worker.is_event_processed",
        lambda db, event_id: False,
    )

    monkeypatch.setattr(
        "services.indexer.worker.get_latest_indexed_version",
        lambda db, document_id: 1,
    )

    record_indexed = Mock()
    record_processed = Mock()

    monkeypatch.setattr(
        "services.indexer.worker.record_indexed_version",
        record_indexed,
    )

    monkeypatch.setattr(
        "services.indexer.worker.record_processed_event",
        record_processed,
    )

    worker.process_message(message)

    shard_manager.index_document.assert_called_once_with(
        document_id=42,
        tokens=["search"],
        embedding=None,
    )

    record_indexed.assert_called_once_with(
        db=db,
        event=event,
    )

    record_processed.assert_called_once_with(
        db=db,
        event=event,
    )

    consumer.commit.assert_called_once_with(message)


def test_duplicate_event_is_skipped_before_version_check(
    monkeypatch,
):
    worker, db, shard_manager, consumer, analyzer = make_worker()

    event = make_event(version=1)
    message = make_message(event)

    monkeypatch.setattr(
        "services.indexer.worker.is_event_processed",
        lambda db, event_id: True,
    )

    latest_version = Mock()

    monkeypatch.setattr(
        "services.indexer.worker.get_latest_indexed_version",
        latest_version,
    )

    worker.process_message(message)

    latest_version.assert_not_called()
    shard_manager.index_document.assert_not_called()
    analyzer.analyze.assert_not_called()

    consumer.commit.assert_called_once_with(message)


def test_remote_shard_indexing_uses_consistent_hash_routing():
    db = Mock(spec=Session)
    consumer = Mock(spec=DocumentEventConsumer)
    analyzer = Mock(spec=TextAnalyzer)

    router = Mock()
    remote_client = Mock()
    remote_client.shard_id = "shard-1"

    router.get_shard_id.return_value = "shard-1"

    worker = IndexerWorker(
        db=db,
        shard_manager=None,
        consumer=consumer,
        analyzer=analyzer,
        shard_router=router,
        shard_clients={
            "shard-1": remote_client,
        },
    )

    document = make_document()

    db.get.return_value = document

    analyzer.analyze.return_value = [
        "distribut",
        "search",
        "python",
    ]

    with patch(
        "services.indexer.worker.is_event_processed",
        return_value=False,
    ), patch(
        "services.indexer.worker.get_latest_indexed_version",
        return_value=None,
    ), patch(
        "services.indexer.worker.record_indexed_version",
    ), patch(
        "services.indexer.worker.record_processed_event",
    ):
        worker.process_message(
            make_message(
                make_event()
            )
        )

    router.get_shard_id.assert_called_once_with(
        42
    )

    remote_client.index_document.assert_called_once_with(
        document_id=42,
        tokens=[
            "distribut",
            "search",
            "python",
        ],
        embedding=None,
    )


def test_remote_shard_delete_uses_consistent_hash_routing():
    db = Mock(spec=Session)
    consumer = Mock(spec=DocumentEventConsumer)
    analyzer = Mock(spec=TextAnalyzer)

    router = Mock()
    remote_client = Mock()
    remote_client.shard_id = "shard-1"

    router.get_shard_id.return_value = "shard-1"

    worker = IndexerWorker(
        db=db,
        shard_manager=None,
        consumer=consumer,
        analyzer=analyzer,
        shard_router=router,
        shard_clients={
            "shard-1": remote_client,
        },
    )

    worker.process_event(
        make_event(
            event_type=DocumentEventType.DELETED,
            content_hash=None,
        )
    )

    router.get_shard_id.assert_called_once_with(
        42
    )

    remote_client.delete_document.assert_called_once_with(
        document_id=42
    )