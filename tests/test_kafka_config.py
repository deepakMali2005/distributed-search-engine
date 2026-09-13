import pytest

from libs.common.kafka import KafkaConfig


def test_default_kafka_configuration(monkeypatch):
    monkeypatch.delenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        raising=False,
    )
    monkeypatch.delenv(
        "KAFKA_DOCUMENT_EVENTS_TOPIC",
        raising=False,
    )
    monkeypatch.delenv(
        "KAFKA_INDEXER_GROUP_ID",
        raising=False,
    )

    config = KafkaConfig.from_environment()

    assert config.bootstrap_servers == "localhost:9092"
    assert config.document_events_topic == "document-events"
    assert config.indexer_group_id == "indexer-workers"


def test_kafka_configuration_from_environment(monkeypatch):
    monkeypatch.setenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "kafka:29092",
    )
    monkeypatch.setenv(
        "KAFKA_DOCUMENT_EVENTS_TOPIC",
        "custom-events",
    )
    monkeypatch.setenv(
        "KAFKA_INDEXER_GROUP_ID",
        "custom-indexer-group",
    )

    config = KafkaConfig.from_environment()

    assert config.bootstrap_servers == "kafka:29092"
    assert config.document_events_topic == "custom-events"
    assert config.indexer_group_id == "custom-indexer-group"


def test_empty_bootstrap_servers_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "",
    )

    with pytest.raises(ValueError):
        KafkaConfig.from_environment()


def test_empty_topic_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "KAFKA_DOCUMENT_EVENTS_TOPIC",
        "",
    )

    with pytest.raises(ValueError):
        KafkaConfig.from_environment()


def test_empty_indexer_group_id_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "KAFKA_INDEXER_GROUP_ID",
        "",
    )

    with pytest.raises(ValueError):
        KafkaConfig.from_environment()