"""
Crawler → Processor → Storage → Event Producer → Indexer pipeline.

Flow:

    Crawler
        ↓
    Processor
        ↓
    Storage
        ↓
    Change Detection
        ↓
    ├── Document Event Producer → Kafka
    │
    └── Indexer (temporary synchronous compatibility path)

Storage determines whether each document is:

    CREATED
    UPDATED
    UNCHANGED

Only CREATED and UPDATED documents produce Kafka events.

The storage layer remains responsible only for persistence and
change detection. The pipeline coordinates persistence,
event publication, and the temporary synchronous indexer.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentChangeType,
    DocumentEventType,
)
from libs.models import Document
from services.crawler.crawler import Crawler
from services.events.producer import DocumentEventProducer
from services.indexer.indexer import Indexer
from services.processor.processor import clean_text
from services.storage.storage import save_document


@dataclass(frozen=True)
class PipelineResult:
    """
    Result of processing one document through the pipeline.
    """

    document: Document
    change_type: DocumentChangeType

    @property
    def changed(self) -> bool:
        """
        Return True when the document changed and needs processing.
        """

        return self.change_type in {
            DocumentChangeType.CREATED,
            DocumentChangeType.UPDATED,
        }


def _create_document_event(
    document: Document,
    change_type: DocumentChangeType,
) -> DocumentChangeEvent | None:
    """
    Create a Kafka document event for a stored document.

    UNCHANGED documents do not produce events.
    """

    if change_type == DocumentChangeType.CREATED:
        event_type = DocumentEventType.CREATED

    elif change_type == DocumentChangeType.UPDATED:
        event_type = DocumentEventType.UPDATED

    else:
        return None

    return DocumentChangeEvent.create(
        event_type=event_type,
        document_id=document.id,
        url=document.url,
        content_hash=document.content_hash,
        event_version=document.version,
    )


def crawl_and_store(
    db: Session,
    start_url: str,
    max_pages: int = 10,
    max_depth: int | None = None,
    indexer: Indexer | None = None,
    event_producer: DocumentEventProducer | None = None,
) -> list[PipelineResult]:
    """
    Crawl, process, store, publish document events, and optionally index.

    CREATED documents:
        - are published to Kafka as CREATED events
        - are indexed synchronously when an Indexer is provided

    UPDATED documents:
        - are published to Kafka as UPDATED events
        - are re-indexed synchronously when an Indexer is provided

    UNCHANGED documents:
        - do not produce Kafka events
        - are not indexed

    Args:
        db:
            PostgreSQL database session.

        start_url:
            URL from which crawling begins.

        max_pages:
            Maximum number of pages to crawl.

        max_depth:
            Maximum link depth from the starting URL.

            0:
                Crawl only the starting URL.

            1:
                Crawl the starting URL and its direct links.

            None:
                No depth restriction.

        indexer:
            Optional synchronous indexer retained temporarily
            during the migration to Kafka-based indexing.

        event_producer:
            Optional Kafka document event producer.

            Dependency injection is used here so tests can provide
            a mock producer without requiring Kafka.
    """

    crawler = Crawler()

    crawled_documents = crawler.crawl(
        start_url=start_url,
        max_pages=max_pages,
        max_depth=max_depth,
    )

    results: list[PipelineResult] = []

    for document in crawled_documents:

        processed_text = clean_text(
            document["text"]
        )

        saved_document, change_type = save_document(
            db=db,
            url=document["url"],
            title=document["title"],
            content=processed_text,
            content_type="text/html",
        )

        # Publish a Kafka event for newly created or changed documents.
        if event_producer is not None:
            event = _create_document_event(
                document=saved_document,
                change_type=change_type,
            )

            if event is not None:
                event_producer.publish(event)

        # Temporary synchronous indexing path.
        #
        # This remains during the migration to the Kafka-based
        # distributed indexing pipeline.
        if (
            indexer is not None
            and change_type
            in {
                DocumentChangeType.CREATED,
                DocumentChangeType.UPDATED,
            }
        ):
            indexer.index_document(
                document_id=saved_document.id,
                content=saved_document.content,
            )

        results.append(
            PipelineResult(
                document=saved_document,
                change_type=change_type,
            )
        )

    return results