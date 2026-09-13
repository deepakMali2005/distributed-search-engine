from unittest.mock import Mock

from confluent_kafka import Consumer

from libs.common.kafka import KafkaConfig
from services.events.consumer import DocumentEventConsumer


def make_config() -> KafkaConfig:
    return KafkaConfig(
        bootstrap_servers="localhost:9092",
        document_events_topic="document-events",
        indexer_group_id="test-indexer-workers",
    )


def test_consumer_uses_kafka_configuration():
    consumer = DocumentEventConsumer(
        make_config()
    )

    assert consumer.config == make_config()

    consumer.close()


def test_consumer_uses_configured_group_id():
    consumer = DocumentEventConsumer(
        make_config()
    )

    assert (
        consumer.consumer_group_id
        == "test-indexer-workers"
    )

    consumer.close()


def test_consumer_subscribes_to_document_events_topic():
    consumer = DocumentEventConsumer(
        make_config()
    )

    mock_consumer = Mock(spec=Consumer)
    consumer._consumer = mock_consumer

    consumer.subscribe()

    mock_consumer.subscribe.assert_called_once_with(
        ["document-events"]
    )


def test_consumer_commits_message_synchronously():
    consumer = DocumentEventConsumer(
        make_config()
    )

    mock_consumer = Mock(spec=Consumer)
    consumer._consumer = mock_consumer

    message = Mock()

    consumer.commit(message)

    mock_consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )