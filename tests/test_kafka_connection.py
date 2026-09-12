from confluent_kafka import Producer

from libs.common.kafka import KafkaConfig


def test_kafka_broker_is_reachable():
    config = KafkaConfig.from_environment()

    producer = Producer(
        {
            "bootstrap.servers": config.bootstrap_servers,
        }
    )

    metadata = producer.list_topics(timeout=5)

    assert metadata.brokers