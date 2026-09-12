from dataclasses import dataclass
import os


@dataclass(frozen=True)
class KafkaConfig:
    """
    Configuration required to connect to Kafka.
    """

    bootstrap_servers: str
    document_events_topic: str

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

        if not bootstrap_servers:
            raise ValueError(
                "KAFKA_BOOTSTRAP_SERVERS must not be empty"
            )

        if not document_events_topic:
            raise ValueError(
                "KAFKA_DOCUMENT_EVENTS_TOPIC must not be empty"
            )

        return cls(
            bootstrap_servers=bootstrap_servers,
            document_events_topic=document_events_topic,
        )