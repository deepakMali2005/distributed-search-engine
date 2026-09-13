from __future__ import annotations

from confluent_kafka import Consumer, Message

from libs.common.kafka import KafkaConfig


class DocumentEventConsumer:
    """
    Kafka consumer for the document-events topic.

    This class is responsible only for consuming Kafka messages.
    Document processing belongs to the IndexerWorker.
    """

    def __init__(
        self,
        config: KafkaConfig | None = None,
    ) -> None:
        self.config = (
            config or KafkaConfig.from_environment()
        )

        self._consumer = Consumer(
            {
                "bootstrap.servers": (
                    self.config.bootstrap_servers
                ),
                "group.id": self.config.indexer_group_id,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )

    @property
    def consumer_group_id(self) -> str:
        """
        Return the configured Kafka consumer group ID.
        """

        return self.config.indexer_group_id

    def subscribe(self) -> None:
        """
        Subscribe to the document events topic.
        """

        self._consumer.subscribe(
            [self.config.document_events_topic]
        )

    def poll(
        self,
        timeout: float = 1.0,
    ) -> Message | None:
        """
        Poll Kafka for one message.
        """

        return self._consumer.poll(timeout)

    def commit(
        self,
        message: Message,
    ) -> None:
        """
        Commit the offset for a successfully processed message.
        """

        self._consumer.commit(
            message=message,
            asynchronous=False,
        )

    def close(self) -> None:
        """
        Close the Kafka consumer.
        """

        self._consumer.close()