from __future__ import annotations

from confluent_kafka import Producer

from libs.common.document_events import DocumentChangeEvent
from libs.common.kafka import KafkaConfig


class DocumentEventProducer:
    """
    Publishes DocumentChangeEvent messages to Kafka.
    """

    def __init__(
        self,
        config: KafkaConfig | None = None,
    ) -> None:
        self.config = config or KafkaConfig.from_environment()

        self._producer = Producer(
            {
                "bootstrap.servers": self.config.bootstrap_servers,
            }
        )

    def publish(
        self,
        event: DocumentChangeEvent,
    ) -> None:
        """
        Publish a document event to the main document-events topic.
        """

        self._publish_to_topic(
            topic=self.config.document_events_topic,
            event=event,
        )

    def publish_to_dlq(
        self,
        event: DocumentChangeEvent,
    ) -> None:
        """
        Publish the original document event to the DLQ topic.

        The event payload is intentionally unchanged so the DLQ
        contains the original event that failed processing.
        """

        self._publish_to_topic(
            topic=self.config.document_events_dlq_topic,
            event=event,
        )

    def _publish_to_topic(
        self,
        topic: str,
        event: DocumentChangeEvent,
    ) -> None:
        """
        Publish an event to the specified Kafka topic.
        """

        self._producer.produce(
            topic=topic,
            key=str(event.document_id),
            value=event.to_json(),
        )

        self._producer.flush()