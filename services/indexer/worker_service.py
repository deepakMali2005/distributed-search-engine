from __future__ import annotations

import os
import signal
from types import FrameType

from services.events.consumer import DocumentEventConsumer
from services.indexer.remote_shard_client import (
    HttpShardIndexClient,
)
from services.indexer.shard_router import ShardRouter
from services.indexer.worker import IndexerWorker
from services.search_api.database import SessionLocal


DEFAULT_SHARD_URLS = {
    "shard-0": "http://127.0.0.1:8100",
    "shard-1": "http://127.0.0.1:8101",
    "shard-2": "http://127.0.0.1:8102",
}


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
        """

        self._shutdown_requested = True

    def run(self) -> None:
        """
        Start consuming and processing Kafka events.
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


def _load_shard_urls() -> dict[str, str]:
    """
    Load remote shard URLs from the environment.

    Environment format:

        INDEXER_SHARD_URLS=shard-0=http://127.0.0.1:8100,shard-1=http://127.0.0.1:8101,shard-2=http://127.0.0.1:8102

    If the variable is not supplied, local development defaults
    point to the three shard services used by the smoke tests.
    """

    raw = os.getenv(
        "INDEXER_SHARD_URLS"
    )

    if not raw:
        return dict(
            DEFAULT_SHARD_URLS
        )

    shard_urls: dict[str, str] = {}

    for item in raw.split(","):
        item = item.strip()

        if not item:
            continue

        if "=" not in item:
            raise ValueError(
                "INDEXER_SHARD_URLS entries must use "
                "shard-id=url format."
            )

        shard_id, url = item.split(
            "=",
            1,
        )

        shard_id = shard_id.strip()
        url = url.strip()

        if not shard_id:
            raise ValueError(
                "Shard ID cannot be empty."
            )

        if not url:
            raise ValueError(
                f"URL cannot be empty for {shard_id}."
            )

        shard_urls[shard_id] = url

    if not shard_urls:
        raise ValueError(
            "INDEXER_SHARD_URLS cannot be empty."
        )

    return shard_urls


def create_worker_service() -> IndexerWorkerService:
    """
    Construct a fully configured distributed indexer worker.

    Runtime architecture:

        Kafka
          ↓
        IndexerWorker
          ↓
        ShardRouter
          ↓
        HttpShardIndexClient
          ↓
        Independent shard services
    """

    db = SessionLocal()

    consumer = DocumentEventConsumer()

    shard_urls = _load_shard_urls()

    shard_ids = list(
        shard_urls.keys()
    )

    router = ShardRouter(
        shard_ids=shard_ids
    )

    shard_clients = {
        shard_id: HttpShardIndexClient(
            shard_id=shard_id,
            base_url=url,
        )
        for shard_id, url in shard_urls.items()
    }

    worker = IndexerWorker(
        db=db,
        shard_manager=None,
        consumer=consumer,
        shard_router=router,
        shard_clients=shard_clients,
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