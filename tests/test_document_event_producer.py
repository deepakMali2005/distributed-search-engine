from datetime import datetime, timezone
from unittest.mock import Mock

from confluent_kafka import Producer

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.common.kafka import KafkaConfig
from services.events.producer import DocumentEventProducer


def make_event() -> DocumentChangeEvent:
    return DocumentChangeEvent.create(
        event_type=DocumentEventType.CREATED,
        document_id=42,
        url="https://example.com/test",
        content_hash="abc123",
        occurred_at=datetime(
            2026,
            9,
            12,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_producer_uses_kafka_configuration():
    config = KafkaConfig(
        bootstrap_servers="localhost:9092",
        document_events_topic="document-events",
    )

    producer = DocumentEventProducer(config)

    assert producer.config == config


def test_publish_sends_event_to_kafka():
    config = KafkaConfig(
        bootstrap_servers="localhost:9092",
        document_events_topic="document-events",
    )

    producer = DocumentEventProducer(config)

    mock_kafka_producer = Mock(spec=Producer)
    producer._producer = mock_kafka_producer

    event = make_event()

    producer.publish(event)

    mock_kafka_producer.produce.assert_called_once_with(
        topic="document-events",
        key="42",
        value=event.to_json(),
    )

    mock_kafka_producer.flush.assert_called_once()


def test_publish_uses_document_id_as_key():
    config = KafkaConfig(
        bootstrap_servers="localhost:9092",
        document_events_topic="document-events",
    )

    producer = DocumentEventProducer(config)

    mock_kafka_producer = Mock(spec=Producer)
    producer._producer = mock_kafka_producer

    event = make_event()

    producer.publish(event)

    call = mock_kafka_producer.produce.call_args

    assert call.kwargs["key"] == "42"


def test_publish_serializes_event_using_event_contract():
    config = KafkaConfig(
        bootstrap_servers="localhost:9092",
        document_events_topic="document-events",
    )

    producer = DocumentEventProducer(config)

    mock_kafka_producer = Mock(spec=Producer)
    producer._producer = mock_kafka_producer

    event = make_event()

    producer.publish(event)

    call = mock_kafka_producer.produce.call_args

    assert call.kwargs["value"] == event.to_json()


def test_publish_to_dlq_sends_event_to_dlq_topic():
    config = KafkaConfig(
        bootstrap_servers="localhost:9092",
        document_events_topic="document-events",
        document_events_dlq_topic="document-events-dlq",
    )

    producer = DocumentEventProducer(config)

    mock_kafka_producer = Mock(spec=Producer)
    producer._producer = mock_kafka_producer

    event = make_event()

    producer.publish_to_dlq(event)

    mock_kafka_producer.produce.assert_called_once_with(
        topic="document-events-dlq",
        key="42",
        value=event.to_json(),
    )

    mock_kafka_producer.flush.assert_called_once()