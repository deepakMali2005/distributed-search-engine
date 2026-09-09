"""
Crawler → Processor → Storage pipeline.

This module connects the crawler, processor, and storage layers.

The crawler is responsible for:
    1. Fetching web pages.
    2. Parsing their content.
    3. Returning structured document data.

The processor is responsible for:
    1. Cleaning raw text.
    2. Normalizing whitespace.
    3. Preparing document content for storage and later indexing.

The storage layer is responsible for:
    1. Creating Document objects.
    2. Saving them to PostgreSQL.
    3. Retrieving existing documents.

This pipeline acts as the bridge between all three layers.
"""

from sqlalchemy.orm import Session

from libs.models import Document
from services.crawler.crawler import Crawler
from services.processor.processor import clean_text
from services.storage.storage import (
    get_document_by_url,
    save_document,
)


def crawl_and_store(
    db: Session,
    start_url: str,
    max_pages: int = 10,
) -> list[Document]:
    """
    Crawl web pages, process their content, and store them in PostgreSQL.

    The function performs the following steps:

        Crawler
            ↓
        Crawl web pages
            ↓
        Extract raw document data
            ↓
        Processor
            ↓
        Clean and normalize text
            ↓
        Check whether document already exists
            ↓
        Storage
            ↓
        PostgreSQL

    Args:
        db:
            SQLAlchemy database session used to communicate with PostgreSQL.

        start_url:
            The URL from which the crawler should start.

        max_pages:
            Maximum number of pages the crawler should visit.

    Returns:
        A list of Document objects that were either newly saved
        or already existed in the database.
    """

    # Create the crawler responsible for fetching and parsing
    # web pages.
    crawler = Crawler()

    # Crawl the website and receive structured document data.
    #
    # Each item returned by the crawler looks approximately like:
    #
    # {
    #     "url": "https://example.com",
    #     "title": "Example",
    #     "text": "Page content..."
    # }
    crawled_documents = crawler.crawl(
        start_url=start_url,
        max_pages=max_pages,
    )

    # This list will contain the database Document objects
    # corresponding to the crawled pages.
    saved_documents: list[Document] = []

    for document in crawled_documents:

        # Check whether this URL has already been stored.
        #
        # This prevents the same webpage from being inserted
        # into PostgreSQL multiple times when the crawler is
        # run again.
        existing_document = get_document_by_url(
            db=db,
            url=document["url"],
        )

        if existing_document:
            # The document already exists, so we don't insert
            # another copy into the database.
            saved_documents.append(existing_document)
            continue

        # The document does not exist yet.
        #
        # The crawler gives us raw text. Before storing it,
        # send it through the processor.
        #
        # Example:
        #
        # Raw:
        # "   Hello     Search Engine\n\nWorld   "
        #
        # Processed:
        # "Hello Search Engine World"
        processed_text = clean_text(
            document["text"]
        )

        # Store the processed document in PostgreSQL.
        #
        # The storage layer handles creating the SQLAlchemy
        # Document object and committing it to the database.
        saved_document = save_document(
            db=db,
            url=document["url"],
            title=document["title"],
            content=processed_text,
            content_type="text/html",
        )

        # Keep track of the document that was successfully
        # stored in PostgreSQL.
        saved_documents.append(saved_document)

    return saved_documents