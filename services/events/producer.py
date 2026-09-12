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
        Publish a document change event to Kafka.

        The document_id is used as the Kafka message key so that
        all events for the same document are routed to the same
        partition, preserving their order.
        """

        self._producer.produce(
            topic=self.config.document_events_topic,
            key=str(event.document_id),
            value=event.to_json(),
        )

        self._producer.flush()