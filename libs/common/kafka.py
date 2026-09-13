from dataclasses import dataclass
import os


@dataclass(frozen=True)
class KafkaConfig:
    """
    Configuration required to connect to Kafka.
    """

    bootstrap_servers: str
    document_events_topic: str
    indexer_group_id: str = "indexer-workers"
    document_events_dlq_topic: str = "document-events-dlq"

    @classmethod
    def from_environment(cls) -> "KafkaConfig":
        """
        Load Kafka configuration from environment variables.
        """

        bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        )

        document_events_topic = os.getenv(
            "KAFKA_DOCUMENT_EVENTS_TOPIC",
            "document-events",
        )

        indexer_group_id = os.getenv(
            "KAFKA_INDEXER_GROUP_ID",
            "indexer-workers",
        )

        document_events_dlq_topic = os.getenv(
            "KAFKA_DOCUMENT_EVENTS_DLQ_TOPIC",
            "document-events-dlq",
        )

        if not bootstrap_servers:
            raise ValueError(
                "KAFKA_BOOTSTRAP_SERVERS must not be empty"
            )

        if not document_events_topic:
            raise ValueError(
                "KAFKA_DOCUMENT_EVENTS_TOPIC must not be empty"
            )

        if not indexer_group_id:
            raise ValueError(
                "KAFKA_INDEXER_GROUP_ID must not be empty"
            )

        if not document_events_dlq_topic:
            raise ValueError(
                "KAFKA_DOCUMENT_EVENTS_DLQ_TOPIC must not be empty"
            )

        return cls(
            bootstrap_servers=bootstrap_servers,
            document_events_topic=document_events_topic,
            indexer_group_id=indexer_group_id,
            document_events_dlq_topic=document_events_dlq_topic,
        )