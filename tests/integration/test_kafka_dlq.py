import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, TopicPartition

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.common.kafka import KafkaConfig
from services.events.producer import DocumentEventProducer


def make_event() -> DocumentChangeEvent:
    return DocumentChangeEvent.create(
        event_type=DocumentEventType.CREATED,
        document_id=987655,
        url="https://example.com/kafka-dlq-integration-test",
        content_hash="dlq-integration-test-hash",
        occurred_at=datetime.now(timezone.utc),
    )


def test_document_event_is_published_to_kafka_dlq():
    config = KafkaConfig.from_environment()

    consumer = Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": f"document-event-dlq-integration-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
        }
    )

    try:
        metadata = consumer.list_topics(
            topic=config.document_events_dlq_topic,
            timeout=5,
        )

        topic_metadata = metadata.topics[
            config.document_events_dlq_topic
        ]

        partitions = [
            partition_metadata.id
            for partition_metadata in topic_metadata.partitions.values()
        ]

        assert partitions, "DLQ topic has no partitions"

        # Record the end offset of every partition before publishing.
        offsets_before_publish = {}

        for partition in partitions:
            _, end_offset = consumer.get_watermark_offsets(
                TopicPartition(
                    config.document_events_dlq_topic,
                    partition,
                ),
                timeout=5,
            )

            offsets_before_publish[partition] = end_offset

        producer = DocumentEventProducer(config)
        event = make_event()

        producer.publish_to_dlq(event)

        # Start consuming exactly where the topic was before this
        # test published its event.
        starting_partitions = [
            TopicPartition(
                config.document_events_dlq_topic,
                partition,
                offsets_before_publish[partition],
            )
            for partition in partitions
        ]

        consumer.assign(starting_partitions)

        received = None

        for _ in range(10):
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                continue

            if message.key() != str(event.document_id).encode("utf-8"):
                continue

            received = message
            break

        assert received is not None

        assert (
            received.key().decode("utf-8")
            == str(event.document_id)
        )

        assert (
            received.value().decode("utf-8")
            == event.to_json()
        )

    finally:
        consumer.close()