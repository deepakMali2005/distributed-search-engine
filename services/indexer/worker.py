from __future__ import annotations

import time
from typing import Protocol

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
from services.indexer.shard_router import ShardRouter
from services.semantic.embedding import EmbeddingModel
from services.semantic.models import Embedding
from services.storage.document_index_versions import (
    get_latest_indexed_version,
    record_indexed_version,
)
from services.storage.processed_events import (
    is_event_processed,
    record_processed_event,
)
from services.storage.storage import get_document


class ShardIndexClient(Protocol):
    shard_id: str

    def index_document(
        self,
        document_id: int,
        tokens: list[str],
        embedding: Embedding | None = None,
    ) -> None:
        ...

    def delete_document(
        self,
        document_id: int,
    ) -> None:
        ...


class IndexerWorker:
    """
    Processes document change events from Kafka.

    The worker supports two indexing modes:

    1. Local mode:
        Kafka -> local ShardManager

       Used by unit/integration tests and local in-process
       indexing scenarios.

    2. Distributed mode:
        Kafka -> ShardRouter -> remote shard clients

       Used by the real distributed worker service.

    Kafka provides at-least-once delivery, so events may be delivered
    more than once or out of order.

    PostgreSQL stores:
    - processed event IDs for duplicate-event protection
    - latest indexed document version for stale-event protection

    Bootstrap events are used to repair missing shard state when the
    canonical PostgreSQL document exists but its owning shard does not
    contain the document.
    """

    def __init__(
        self,
        db: Session,
        shard_manager: ShardManager | None,
        consumer: DocumentEventConsumer,
        analyzer: TextAnalyzer | None = None,
        embedding_model: EmbeddingModel | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        dlq_producer: DocumentEventProducer | None = None,
        *,
        shard_router: ShardRouter | None = None,
        shard_clients: dict[str, ShardIndexClient] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError(
                "max_retries must be greater than or equal to 0"
            )

        if retry_delay < 0:
            raise ValueError(
                "retry_delay must be greater than or equal to 0"
            )

        if shard_manager is not None and shard_clients is not None:
            raise ValueError(
                "Provide either shard_manager or shard_clients, not both."
            )

        if shard_clients is not None and not shard_clients:
            raise ValueError(
                "shard_clients cannot be empty."
            )

        if shard_clients is not None and shard_router is None:
            raise ValueError(
                "shard_router is required when shard_clients are provided."
            )

        self.db = db
        self.shard_manager = shard_manager
        self.consumer = consumer
        self.analyzer = analyzer or TextAnalyzer()
        self.embedding_model = embedding_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.dlq_producer = dlq_producer
        self.shard_router = shard_router
        self.shard_clients = shard_clients

    def _index_document(
        self,
        document_id: int,
        tokens: list[str],
        embedding: Embedding | None = None,
    ) -> None:
        """
        Index a document using either the local or distributed
        shard implementation.
        """

        if self.shard_clients is not None:
            assert self.shard_router is not None

            shard_id = self.shard_router.get_shard_id(
                document_id
            )

            client = self.shard_clients.get(
                shard_id
            )

            if client is None:
                raise RuntimeError(
                    f"No shard client configured for {shard_id}"
                )

            client.index_document(
                document_id=document_id,
                tokens=tokens,
                embedding=embedding,
            )

            return

        if self.shard_manager is None:
            raise RuntimeError(
                "No shard indexing backend is configured."
            )

        self.shard_manager.index_document(
            document_id=document_id,
            tokens=tokens,
            embedding=embedding,
        )

    def _delete_document(
        self,
        document_id: int,
    ) -> None:
        """
        Delete a document using either the local or distributed
        shard implementation.
        """

        if self.shard_clients is not None:
            assert self.shard_router is not None

            shard_id = self.shard_router.get_shard_id(
                document_id
            )

            client = self.shard_clients.get(
                shard_id
            )

            if client is None:
                raise RuntimeError(
                    f"No shard client configured for {shard_id}"
                )

            client.delete_document(
                document_id=document_id
            )

            return

        if self.shard_manager is None:
            raise RuntimeError(
                "No shard indexing backend is configured."
            )

        self.shard_manager.remove_document(
            document_id
        )

    @staticmethod
    def _build_lexical_text(
        title: str | None,
        content: str,
    ) -> str:
        """
        Build the text used by the lexical analyzer.

        The document title is included because it is part of the
        searchable document representation.

        Empty titles are ignored.
        """

        title = (title or "").strip()
        content = (content or "").strip()

        if title and content:
            return f"{title}\n{content}"

        return title or content

    def _analyze_document(
        self,
        title: str | None,
        content: str,
    ) -> list[str]:
        """
        Convert the canonical document into lexical index tokens.
        """

        lexical_text = self._build_lexical_text(
            title=title,
            content=content,
        )

        return self.analyzer.analyze(
            lexical_text
        )

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
            self._delete_document(
                event.document_id
            )

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

        tokens = self._analyze_document(
            title=document.title,
            content=document.content,
        )

        embedding = (
            self.embedding_model.embed(
                document.content
            )
            if self.embedding_model is not None
            else None
        )

        self._index_document(
            document_id=event.document_id,
            tokens=tokens,
            embedding=embedding,
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

        return DocumentChangeEvent.from_json(
            payload
        )

    def process_message(
        self,
        message,
    ) -> None:
        error = message.error()

        if error is not None:
            raise RuntimeError(
                f"Kafka consumer error: {error}"
            )

        event = self._deserialize_event(
            message
        )

        # Exact event duplicate.
        if is_event_processed(
            db=self.db,
            event_id=event.event_id,
        ):
            self.consumer.commit(
                message
            )

            return

        # Deleted events do not require a PostgreSQL document lookup.
        if event.event_type == DocumentEventType.DELETED:
            self.process_event(
                event
            )

            record_processed_event(
                db=self.db,
                event=event,
            )

            self.consumer.commit(
                message
            )

            return

        document = get_document(
            db=self.db,
            document_id=event.document_id,
        )

        if document is None:
            raise RuntimeError(
                f"Document {event.document_id} does not exist in PostgreSQL"
            )

        is_bootstrap_event = bool(
            event.metadata.get("bootstrap")
        )

        latest_indexed_version = (
            get_latest_indexed_version(
                db=self.db,
                document_id=event.document_id,
            )
        )

        # Bootstrap events intentionally bypass the previous
        # indexed-version check.
        #
        # This repairs the case where:
        #
        # PostgreSQL index-version = indexed
        # actual shard state    = missing
        #
        # Without this exception, reconciliation could discover the
        # missing shard document but the worker would reject the
        # repair event as stale.
        version_state = classify_event_version(
            event_version=event.event_version,
            latest_indexed_version=(
                None
                if is_bootstrap_event
                else latest_indexed_version
            ),
            document_version=document.version,
        )

        if version_state == EventVersionState.STALE:
            record_processed_event(
                db=self.db,
                event=event,
            )

            self.consumer.commit(
                message
            )

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

        tokens = self._analyze_document(
            title=document.title,
            content=document.content,
        )

        embedding = (
            self.embedding_model.embed(
                document.content
            )
            if self.embedding_model is not None
            else None
        )

        self._index_document(
            document_id=event.document_id,
            tokens=tokens,
            embedding=embedding,
        )

        record_indexed_version(
            db=self.db,
            event=event,
        )

        record_processed_event(
            db=self.db,
            event=event,
        )

        self.consumer.commit(
            message
        )

    def _publish_to_dlq(
        self,
        event: DocumentChangeEvent,
    ) -> None:
        producer = self.dlq_producer

        if producer is None:
            producer = DocumentEventProducer(
                KafkaConfig.from_environment()
            )

        producer.publish_to_dlq(
            event
        )

    def process_message_with_retry(
        self,
        message,
    ) -> None:
        attempts = self.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                self.process_message(
                    message
                )

                return

            except Exception as exc:
                last_error = exc

                if attempt == self.max_retries:
                    break

                if self.retry_delay > 0:
                    time.sleep(
                        self.retry_delay
                    )

        assert last_error is not None

        event = self._deserialize_event(
            message
        )

        self._publish_to_dlq(
            event
        )

        self.consumer.commit(
            message
        )

    def run_once(
        self,
        timeout: float = 1.0,
    ) -> bool:
        message = self.consumer.poll(
            timeout
        )

        if message is None:
            return False

        self.process_message_with_retry(
            message
        )

        return True

    def run(self) -> None:
        """
        Run the worker directly.

        This method is primarily useful for standalone execution.
        The production worker service uses IndexerWorkerService.
        """

        self.consumer.subscribe()

        try:
            while True:
                self.run_once()

        finally:
            self.consumer.close()
