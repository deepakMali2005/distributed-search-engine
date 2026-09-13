from __future__ import annotations

import time

from sqlalchemy.orm import Session

from libs.common.document_event_version import (
    EventVersionState,
    classify_event_version,
)
from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.common.kafka import KafkaConfig
from services.events.consumer import DocumentEventConsumer
from services.events.producer import DocumentEventProducer
from services.indexer.analyzer import TextAnalyzer
from services.indexer.shard_manager import ShardManager
from services.storage.document_index_versions import (
    get_latest_indexed_version,
    record_indexed_version,
)
from services.storage.processed_events import (
    is_event_processed,
    record_processed_event,
)
from services.storage.storage import get_document


class IndexerWorker:
    """
    Processes document change events from Kafka.

    Kafka provides at-least-once delivery, so events may be delivered
    more than once or out of order.

    PostgreSQL stores:
    - processed event IDs for duplicate-event protection
    - latest indexed document version for stale-event protection
    """

    def __init__(
        self,
        db: Session,
        shard_manager: ShardManager,
        consumer: DocumentEventConsumer,
        analyzer: TextAnalyzer | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        dlq_producer: DocumentEventProducer | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError(
                "max_retries must be greater than or equal to 0"
            )

        if retry_delay < 0:
            raise ValueError(
                "retry_delay must be greater than or equal to 0"
            )

        self.db = db
        self.shard_manager = shard_manager
        self.consumer = consumer
        self.analyzer = analyzer or TextAnalyzer()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.dlq_producer = dlq_producer

    def process_event(
        self,
        event: DocumentChangeEvent,
    ) -> bool:
        """
        Apply an event to the search index.

        Returns True when the event is applied.

        Returns False when the event is stale and intentionally
        ignored.
        """

        if event.event_type == DocumentEventType.DELETED:
            self.shard_manager.remove_document(event.document_id)
            return True

        document = get_document(
            db=self.db,
            document_id=event.document_id,
        )

        if document is None:
            raise RuntimeError(
                f"Document {event.document_id} does not exist in PostgreSQL"
            )

        if document.version > event.event_version:
            return False

        if document.version < event.event_version:
            raise RuntimeError(
                f"Document version mismatch for document "
                f"{event.document_id}: "
                f"event={event.event_version}, "
                f"database={document.version}"
            )

        if document.content_hash != event.content_hash:
            raise RuntimeError(
                f"Document content hash mismatch for document "
                f"{event.document_id}"
            )

        tokens = self.analyzer.analyze(document.content)

        self.shard_manager.index_document(
            document_id=event.document_id,
            tokens=tokens,
        )

        return True

    def _deserialize_event(
        self,
        message,
    ) -> DocumentChangeEvent:
        payload = message.value()

        if payload is None:
            raise ValueError(
                "Kafka document event message has no payload"
            )

        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        if not isinstance(payload, str):
            raise ValueError(
                "Kafka document event payload must be bytes or string"
            )

        return DocumentChangeEvent.from_json(payload)

    def process_message(
        self,
        message,
    ) -> None:
        error = message.error()

        if error is not None:
            raise RuntimeError(
                f"Kafka consumer error: {error}"
            )

        event = self._deserialize_event(message)

        # Exact event duplicate.
        if is_event_processed(
            db=self.db,
            event_id=event.event_id,
        ):
            self.consumer.commit(message)
            return

        # DELETED events are handled directly because there is no
        # canonical document to read after deletion.
        if event.event_type == DocumentEventType.DELETED:
            self.process_event(event)

            record_processed_event(
                db=self.db,
                event=event,
            )

            self.consumer.commit(message)
            return

        document = get_document(
            db=self.db,
            document_id=event.document_id,
        )

        if document is None:
            raise RuntimeError(
                f"Document {event.document_id} does not exist in PostgreSQL"
            )

        latest_indexed_version = get_latest_indexed_version(
            db=self.db,
            document_id=event.document_id,
        )

        version_state = classify_event_version(
            event_version=event.event_version,
            latest_indexed_version=latest_indexed_version,
            document_version=document.version,
        )

        if version_state == EventVersionState.STALE:
            record_processed_event(
                db=self.db,
                event=event,
            )

            self.consumer.commit(message)
            return

        if version_state == EventVersionState.FUTURE:
            raise RuntimeError(
                f"Document version mismatch for document "
                f"{event.document_id}: "
                f"event={event.event_version}, "
                f"database={document.version}"
            )

        if document.content_hash != event.content_hash:
            raise RuntimeError(
                f"Document content hash mismatch for document "
                f"{event.document_id}"
            )

        tokens = self.analyzer.analyze(document.content)

        self.shard_manager.index_document(
            document_id=event.document_id,
            tokens=tokens,
        )

        record_indexed_version(
            db=self.db,
            event=event,
        )

        record_processed_event(
            db=self.db,
            event=event,
        )

        self.consumer.commit(message)

    def _publish_to_dlq(
        self,
        event: DocumentChangeEvent,
    ) -> None:
        producer = self.dlq_producer

        if producer is None:
            producer = DocumentEventProducer(
                KafkaConfig.from_environment()
            )

        producer.publish_to_dlq(event)

    def process_message_with_retry(
        self,
        message,
    ) -> None:
        attempts = self.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                self.process_message(message)
                return

            except Exception as exc:
                last_error = exc

                if attempt == self.max_retries:
                    break

                if self.retry_delay > 0:
                    time.sleep(self.retry_delay)

        assert last_error is not None

        event = self._deserialize_event(message)

        self._publish_to_dlq(event)

        self.consumer.commit(message)

    def run_once(
        self,
        timeout: float = 1.0,
    ) -> bool:
        message = self.consumer.poll(timeout)

        if message is None:
            return False

        self.process_message_with_retry(message)

        return True

    def run(self) -> None:
        self.consumer.subscribe()

        try:
            while True:
                self.run_once()

        finally:
            self.consumer.close()