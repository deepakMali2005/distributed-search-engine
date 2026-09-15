from __future__ import annotations

import os
import time

from sqlalchemy.orm import Session

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from services.events.producer import DocumentEventProducer
from services.indexer.remote_shard_client import HttpShardIndexClient
from services.indexer.shard_router import ShardRouter
from services.storage.storage import get_all_documents


DEFAULT_SHARD_URLS = {
    "shard-0": "http://127.0.0.1:8100",
    "shard-1": "http://127.0.0.1:8101",
    "shard-2": "http://127.0.0.1:8102",
}


class IndexBootstrapper:
    """
    Reconcile canonical PostgreSQL documents with distributed shards.

    PostgreSQL remains the canonical document store.

    The bootstrapper does not perform indexing itself. It only publishes
    document events for documents that are missing from their owning shard.

    The normal Kafka indexer worker performs the actual lexical and
    semantic indexing.
    """

    def __init__(
        self,
        db: Session,
        event_producer: DocumentEventProducer,
        shard_router: ShardRouter,
        shard_clients: dict[str, HttpShardIndexClient],
        *,
        wait_timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        if not shard_clients:
            raise ValueError(
                "shard_clients cannot be empty."
            )

        if wait_timeout_seconds < 0:
            raise ValueError(
                "wait_timeout_seconds must be >= 0."
            )

        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be > 0."
            )

        self.db = db
        self.event_producer = event_producer
        self.shard_router = shard_router
        self.shard_clients = shard_clients
        self.wait_timeout_seconds = wait_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def find_missing_documents(self) -> list[int]:
        """
        Return document IDs that are not currently present on their
        owning shards.
        """

        missing_document_ids: list[int] = []

        for document in get_all_documents(self.db):
            shard_id = self.shard_router.get_shard_id(
                document.id
            )

            client = self.shard_clients.get(shard_id)

            if client is None:
                raise RuntimeError(
                    f"No shard client configured for {shard_id}"
                )

            if not client.contains_document(document.id):
                missing_document_ids.append(document.id)

        return missing_document_ids

    def bootstrap(
        self,
        document_ids: list[int],
    ) -> int:
        """
        Publish repair events for the supplied documents.

        Returns the number of events published.
        """

        if not document_ids:
            return 0

        documents = {
            document.id: document
            for document in get_all_documents(self.db)
        }

        published = 0

        for document_id in document_ids:
            document = documents.get(document_id)

            if document is None:
                raise RuntimeError(
                    f"Document {document_id} does not exist in PostgreSQL."
                )

            event_type = (
                DocumentEventType.CREATED
                if document.version == 1
                else DocumentEventType.UPDATED
            )

            event = DocumentChangeEvent.create(
                event_type=event_type,
                document_id=document.id,
                url=document.url,
                content_hash=document.content_hash,
                event_version=document.version,
                metadata={
                    "bootstrap": True,
                },
            )

            self.event_producer.publish(event)
            published += 1

        return published

    def wait_for_indexing(
        self,
        document_ids: list[int],
    ) -> None:
        """
        Wait until every requested document is present on its owning shard.
        """

        if not document_ids:
            return

        deadline = (
            time.monotonic()
            + self.wait_timeout_seconds
        )

        pending = set(document_ids)

        while pending:
            for document_id in list(pending):
                shard_id = self.shard_router.get_shard_id(
                    document_id
                )

                client = self.shard_clients.get(shard_id)

                if client is None:
                    raise RuntimeError(
                        f"No shard client configured for {shard_id}"
                    )

                if client.contains_document(document_id):
                    pending.remove(document_id)

            if not pending:
                return

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Timed out waiting for bootstrap indexing of "
                    f"documents: {sorted(pending)}"
                )

            time.sleep(
                self.poll_interval_seconds
            )


def _load_shard_urls() -> dict[str, str]:
    raw = os.getenv(
        "INDEXER_SHARD_URLS"
    )

    if not raw:
        return dict(DEFAULT_SHARD_URLS)

    shard_urls: dict[str, str] = {}

    for item in raw.split(","):
        item = item.strip()

        if not item:
            continue

        if "=" not in item:
            raise ValueError(
                "INDEXER_SHARD_URLS entries must use shard-id=url format."
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


def main() -> None:
    from services.search_api.database import SessionLocal

    db = SessionLocal()

    try:
        shard_urls = _load_shard_urls()

        router = ShardRouter(
            shard_ids=list(shard_urls)
        )

        clients = {
            shard_id: HttpShardIndexClient(
                shard_id=shard_id,
                base_url=url,
            )
            for shard_id, url in shard_urls.items()
        }

        bootstrapper = IndexBootstrapper(
            db=db,
            event_producer=DocumentEventProducer(),
            shard_router=router,
            shard_clients=clients,
            wait_timeout_seconds=float(
                os.getenv(
                    "INDEX_BOOTSTRAP_TIMEOUT_SECONDS",
                    "120",
                )
            ),
            poll_interval_seconds=float(
                os.getenv(
                    "INDEX_BOOTSTRAP_POLL_INTERVAL_SECONDS",
                    "1",
                )
            ),
        )

        missing_document_ids = (
            bootstrapper.find_missing_documents()
        )

        if not missing_document_ids:
            print(
                "Index bootstrap completed: "
                "0 repair event(s) required."
            )
            return

        published = bootstrapper.bootstrap(
            missing_document_ids
        )

        bootstrapper.wait_for_indexing(
            missing_document_ids
        )

        print(
            "Index bootstrap completed: "
            f"{published} repair event(s) published "
            "and verified."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()