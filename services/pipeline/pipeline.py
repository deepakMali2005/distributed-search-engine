"""
Crawler → Processor → Storage → Indexer pipeline.

Flow:

    Crawler
        ↓
    Processor
        ↓
    Storage
        ↓
    Change Detection
        ↓
    Indexer
        ↓
    Inverted Index

Storage determines whether each document is:

    CREATED
    UPDATED
    UNCHANGED

Only CREATED and UPDATED documents are sent
to the indexing layer.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from libs.common.document_events import DocumentChangeType
from libs.models import Document
from services.crawler.crawler import Crawler
from services.processor.processor import clean_text
from services.storage.storage import save_document
from services.indexer.indexer import Indexer


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
        Return True when the document needs indexing.
        """

        return self.change_type in {
            DocumentChangeType.CREATED,
            DocumentChangeType.UPDATED,
        }


def crawl_and_store(
    db: Session,
    start_url: str,
    max_pages: int = 10,
    indexer: Indexer | None = None,
) -> list[PipelineResult]:
    """
    Crawl, process, store, and optionally index documents.

    CREATED documents are indexed.

    UPDATED documents are re-indexed.

    UNCHANGED documents are not indexed.

    The indexer is optional so the storage pipeline can still
    be used independently when indexing is not required.
    """

    crawler = Crawler()

    crawled_documents = crawler.crawl(
        start_url=start_url,
        max_pages=max_pages,
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

        # Only index documents that are new or changed.
        if indexer is not None and change_type in {
            DocumentChangeType.CREATED,
            DocumentChangeType.UPDATED,
        }:
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