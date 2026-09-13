from __future__ import annotations

import signal
from types import FrameType

from services.events.consumer import DocumentEventConsumer
from services.indexer.shard_manager import ShardManager
from services.indexer.worker import IndexerWorker
from services.search_api.database import SessionLocal


class IndexerWorkerService:
    """
    Runtime service for a distributed Kafka indexer worker.

    Multiple instances of this service can run simultaneously.
    Kafka's consumer group distributes topic partitions across
    those instances automatically.
    """

    def __init__(
        self,
        worker: IndexerWorker,
        consumer: DocumentEventConsumer,
        db,
    ) -> None:
        self.worker = worker
        self.consumer = consumer
        self.db = db
        self._shutdown_requested = False

    def request_shutdown(
        self,
        signum: int | None = None,
        frame: FrameType | None = None,
    ) -> None:
        """
        Request a graceful service shutdown.

        The worker loop checks this flag between Kafka polls.
        """
        self._shutdown_requested = True

    def run(self) -> None:
        """
        Start consuming and processing Kafka events.

        The service exits cleanly once shutdown has been requested.
        """
        self.consumer.subscribe()

        try:
            while not self._shutdown_requested:
                self.worker.run_once()

        finally:
            self.close()

    def close(self) -> None:
        """
        Release service resources.
        """
        self.consumer.close()
        self.db.close()


def create_worker_service() -> IndexerWorkerService:
    """
    Construct a fully configured indexer worker service.
    """
    db = SessionLocal()

    consumer = DocumentEventConsumer()

    shard_manager = ShardManager(
        shard_ids=["shard-0", "shard-1", "shard-2"],
    )

    worker = IndexerWorker(
        db=db,
        shard_manager=shard_manager,
        consumer=consumer,
    )

    return IndexerWorkerService(
        worker=worker,
        consumer=consumer,
        db=db,
    )


def main() -> None:
    """
    Application entrypoint for an indexer worker process.
    """
    service = create_worker_service()

    signal.signal(
        signal.SIGINT,
        service.request_shutdown,
    )
    signal.signal(
        signal.SIGTERM,
        service.request_shutdown,
    )

    service.run()


if __name__ == "__main__":
    main()