import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, TopicPartition

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.common.kafka import KafkaConfig
from libs.models import Document
from services.events.consumer import DocumentEventConsumer
from services.events.producer import DocumentEventProducer
from services.indexer.analyzer import TextAnalyzer
from services.indexer.shard_manager import ShardManager
from services.indexer.worker import IndexerWorker
from services.search_api.database import SessionLocal
from services.storage.storage import save_document


def test_kafka_event_is_consumed_and_indexed():
    config = KafkaConfig.from_environment()

    db = SessionLocal()
    document_id = None
    worker_consumer = None

    consumer_group_id = (
        f"worker-integration-{uuid.uuid4()}"
    )

    consumer = Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": consumer_group_id,
            "auto.offset.reset": "earliest",
        }
    )

    try:
        document, _ = save_document(
            db=db,
            url=(
                "https://example.com/"
                f"kafka-worker-{uuid.uuid4()}"
            ),
            title="Kafka Worker Integration Test",
            content=(
                "distributed search kafka indexing"
            ),
            content_type="text/html",
        )

        document_id = document.id

        event = DocumentChangeEvent.create(
            event_type=DocumentEventType.CREATED,
            document_id=document.id,
            url=document.url,
            content_hash=document.content_hash,
            event_version=document.version,
            occurred_at=datetime.now(
                timezone.utc
            ),
        )

        metadata = consumer.list_topics(
            topic=config.document_events_topic,
            timeout=5,
        )

        topic_metadata = metadata.topics[
            config.document_events_topic
        ]

        partitions = list(
            topic_metadata.partitions.keys()
        )

        offsets_before_publish = {}

        for partition in partitions:
            _, end_offset = (
                consumer.get_watermark_offsets(
                    TopicPartition(
                        config.document_events_topic,
                        partition,
                    ),
                    timeout=5,
                )
            )

            offsets_before_publish[partition] = (
                end_offset
            )

        producer = DocumentEventProducer(config)
        producer.publish(event)

        consumer.assign(
            [
                TopicPartition(
                    config.document_events_topic,
                    partition,
                    offsets_before_publish[partition],
                )
                for partition in partitions
            ]
        )

        message = None

        for _ in range(10):
            candidate = consumer.poll(1.0)

            if candidate is None:
                continue

            if candidate.error():
                continue

            if (
                candidate.key()
                != str(document.id).encode("utf-8")
            ):
                continue

            message = candidate
            break

        assert message is not None

        worker_consumer = DocumentEventConsumer(
            config
        )

        shard_manager = ShardManager(
            shard_ids=[
                "shard-1",
                "shard-2",
                "shard-3",
            ],
        )

        worker = IndexerWorker(
            db=db,
            shard_manager=shard_manager,
            consumer=worker_consumer,
            analyzer=TextAnalyzer(),
        )

        worker.process_message(message)

        shard = (
            shard_manager.get_shard_for_document(
                document.id
            )
        )

        assert shard.contains_document(
            document.id
        )

        results = shard.search(
            query="kafka",
            limit=10,
        )

        result_document_ids = {
            result.doc_id
            for result in results
        }

        assert document.id in result_document_ids

        worker_consumer.close()
        worker_consumer = None

    finally:
        consumer.close()

        if worker_consumer is not None:
            worker_consumer.close()

        if document_id is not None:
            document = db.get(
                Document,
                document_id,
            )

            if document is not None:
                db.delete(document)
                db.commit()

        db.close()