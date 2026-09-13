from __future__ import annotations

import time
import uuid

from confluent_kafka import Consumer

from libs.common.kafka import KafkaConfig


def _create_consumer(
    config: KafkaConfig,
    group_id: str,
    instance_id: str,
) -> Consumer:
    consumer = Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": group_id,
            "client.id": instance_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "latest",
        }
    )

    consumer.subscribe([config.document_events_topic])

    return consumer


def test_multiple_workers_receive_distributed_partition_assignments():
    config = KafkaConfig.from_environment()

    group_id = (
        f"{config.indexer_group_id}-distribution-{uuid.uuid4()}"
    )

    consumers = [
        _create_consumer(
            config=config,
            group_id=group_id,
            instance_id=f"worker-{index}",
        )
        for index in range(3)
    ]

    try:
        deadline = time.monotonic() + 15

        stable_assignments: dict[
            str,
            set[tuple[str, int]],
        ] | None = None

        while time.monotonic() < deadline:
            for consumer in consumers:
                consumer.poll(0.2)

            current_assignments = {
                f"worker-{index}": {
                    (partition.topic, partition.partition)
                    for partition in consumer.assignment()
                }
                for index, consumer in enumerate(consumers)
            }

            assigned_partitions = [
                partition
                for partitions in current_assignments.values()
                for partition in partitions
            ]

            if (
                len(assigned_partitions) == 3
                and len(set(assigned_partitions)) == 3
                and len(
                    [
                        partitions
                        for partitions in current_assignments.values()
                        if partitions
                    ]
                )
                >= 2
            ):
                if stable_assignments == current_assignments:
                    break

                stable_assignments = current_assignments

            time.sleep(0.1)

        assert stable_assignments is not None

        assigned_partitions = [
            partition
            for partitions in stable_assignments.values()
            for partition in partitions
        ]

        assert len(assigned_partitions) == 3
        assert len(set(assigned_partitions)) == 3

        active_workers = [
            worker
            for worker, partitions in stable_assignments.items()
            if partitions
        ]

        assert len(active_workers) >= 2

        expected_partitions = {
            (config.document_events_topic, 0),
            (config.document_events_topic, 1),
            (config.document_events_topic, 2),
        }

        assert set(assigned_partitions) == expected_partitions

    finally:
        for consumer in consumers:
            consumer.close()