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
from services.storage.crawl_storage import CrawlStorage
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
    resume: bool = False,
) -> list[PipelineResult]:
    """
    Crawl, process, store, publish document events, and optionally index.

    When resume=True, the crawler uses the persistent PostgreSQL
    frontier and resumes previous crawl progress.
    """

    crawler = Crawler()

    if resume:
        crawled_documents = crawler.crawl_resumable(
            db=db,
            start_url=start_url,
            max_pages=max_pages,
            max_depth=max_depth,
        )

        crawl_storage = CrawlStorage()

    else:
        crawled_documents = crawler.crawl(
            start_url=start_url,
            max_pages=max_pages,
            max_depth=max_depth,
        )

        crawl_storage = None

    results: list[PipelineResult] = []

    for document in crawled_documents:

        frontier_id = document.get(
            "_frontier_id"
        )

        try:
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

            if event_producer is not None:
                event = _create_document_event(
                    document=saved_document,
                    change_type=change_type,
                )

                if event is not None:
                    event_producer.publish(
                        event
                    )

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

            if (
                resume
                and crawl_storage is not None
                and frontier_id is not None
            ):
                crawl_storage.mark_completed(
                    db=db,
                    frontier_id=frontier_id,
                )

        except Exception as exc:

            if (
                resume
                and crawl_storage is not None
                and frontier_id is not None
            ):
                crawl_storage.mark_failed(
                    db=db,
                    frontier_id=frontier_id,
                    error=str(exc),
                )

            raise

    if (
        resume
        and crawl_storage is not None
        and crawled_documents
    ):
        session_id = crawled_documents[0].get(
            "_crawl_session_id"
        )

        if (
            session_id is not None
            and crawl_storage.pending_count(
                db=db,
                crawl_session_id=session_id,
            ) == 0
        ):
            crawl_storage.mark_session_completed(
                db=db,
                crawl_session_id=session_id,
            )

    return results