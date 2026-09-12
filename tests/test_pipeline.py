"""
Integration tests for the Crawler → Storage → PostgreSQL pipeline.

These tests verify that data can successfully travel through
the complete ingestion pipeline:

    Crawler
       ↓
    Pipeline
       ↓
    Storage
       ↓
    PostgreSQL
"""

from unittest.mock import patch
from unittest.mock import Mock

from services.pipeline.pipeline import crawl_and_store
from services.search_api.database import SessionLocal
from services.storage.storage import get_document_by_url
from libs.common.document_events import (
    DocumentChangeType,
    DocumentEventType,
)
from services.indexer.indexer import Indexer


# A small HTML page used as fake crawler input.
#
# We don't want this test to depend on the real internet.
# Instead, we'll make the crawler behave as if it received
# this HTML from a real website.
MOCK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Distributed Search Engine</title>
</head>
<body>
    <h1>Welcome to our search engine</h1>
    <p>This is a test document.</p>
</body>
</html>
"""


def test_crawl_and_store():
    """
    Verify the complete crawler → storage → PostgreSQL pipeline.

    The test:
        1. Mocks the HTTP response.
        2. Runs the real crawler.
        3. Sends the crawled document through the pipeline.
        4. Stores it in the real PostgreSQL database.
        5. Reads it back from PostgreSQL.
        6. Verifies that the stored data is correct.
    """

    test_url = "https://example.com/test-page"

    # Create a database session.
    db = SessionLocal()

    try:
        # Mock the crawler's HTTP request.
        #
        # The crawler itself is still being used normally.
        # Only the external network request is replaced with
        # our controlled HTML.
        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            # Run the complete pipeline.
            documents = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
            )

        # The crawler should have produced exactly one document.
        assert len(documents) == 1

        result = documents[0]

        document = result.document

        # Verify that the crawler extracted the correct information.
        assert document.url == test_url

        assert document.title == "Distributed Search Engine"
        assert "This is a test document." in document.content

        # Verify that the document actually exists in PostgreSQL.
        stored_document = get_document_by_url(
            db=db,
            url=test_url,
        )

        assert stored_document is not None
        assert stored_document.id == document.id
        assert stored_document.url == test_url
        assert stored_document.title == "Distributed Search Engine"

    finally:
        # Always close the database session, even if the test fails.
        db.close()

def test_pipeline_indexes_created_document():
    db = SessionLocal()

    test_url = "https://example.com/incremental-created"

    try:
        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            indexer = Indexer()

            results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                indexer=indexer,
            )

        assert len(results) == 1

        result = results[0]

        assert result.change_type == DocumentChangeType.CREATED
        assert result.changed is True

        postings = indexer.get_index().get_postings("test")

        assert any(
            posting.doc_id == result.document.id
            for posting in postings
        )

    finally:
        document = get_document_by_url(
            db=db,
            url=test_url,
        )

        if document is not None:
            db.delete(document)
            db.commit()

        db.close()

def test_pipeline_reindexes_updated_document():
    db = SessionLocal()

    test_url = "https://example.com/incremental-updated"

    try:
        indexer = Indexer()

        first_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Original</title>
        </head>
        <body>
            <p>Python programming language.</p>
        </body>
        </html>
        """

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = first_html
            mock_get.return_value.raise_for_status.return_value = None

            first_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                indexer=indexer,
            )

        first_result = first_results[0]

        assert first_result.change_type == DocumentChangeType.CREATED

        document_id = first_result.document.id

        # Verify old content is indexed.
        old_postings = indexer.get_index().get_postings(
            "python"
        )

        assert any(
            posting.doc_id == document_id
            for posting in old_postings
        )

        second_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Updated</title>
        </head>
        <body>
            <p>Distributed systems search engine.</p>
        </body>
        </html>
        """

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = second_html
            mock_get.return_value.raise_for_status.return_value = None

            second_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                indexer=indexer,
            )

        second_result = second_results[0]

        assert second_result.change_type == DocumentChangeType.UPDATED
        assert second_result.document.id == document_id

        # Old term should no longer be indexed.
        old_postings = indexer.get_index().get_postings(
            "python"
        )

        assert not any(
            posting.doc_id == document_id
            for posting in old_postings
        )

        # New term should be indexed.
        new_postings = indexer.get_index().get_postings(
            "distribut"
        )

        assert any(
            posting.doc_id == document_id
            for posting in new_postings
        )

    finally:
        document = get_document_by_url(
            db=db,
            url=test_url,
        )

        if document is not None:
            db.delete(document)
            db.commit()

        db.close()


def test_pipeline_skips_unchanged_document():
    db = SessionLocal()

    test_url = "https://example.com/incremental-unchanged"

    try:
        indexer = Indexer()

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            first_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                indexer=indexer,
            )

        first_result = first_results[0]

        assert first_result.change_type == DocumentChangeType.CREATED

        document_id = first_result.document.id

        # Remove the document from the index manually.
        indexer.remove_document(document_id)

        assert indexer.get_index().get_postings("test") == []

        # Crawl the exact same content again.
        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            second_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                indexer=indexer,
            )

        second_result = second_results[0]

        assert second_result.change_type == DocumentChangeType.UNCHANGED
        assert second_result.changed is False

        # Because the document was unchanged, the pipeline
        # should NOT have indexed it again.
        assert indexer.get_index().get_postings("test") == []

    finally:
        document = get_document_by_url(
            db=db,
            url=test_url,
        )

        if document is not None:
            db.delete(document)
            db.commit()

        db.close()

def test_pipeline_publishes_created_event():
    db = SessionLocal()

    test_url = "https://example.com/kafka-created"

    try:
        event_producer = Mock()

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                event_producer=event_producer,
            )

        assert len(results) == 1

        result = results[0]

        assert result.change_type == DocumentChangeType.CREATED
        assert result.document.version == 1

        event_producer.publish.assert_called_once()

        event = event_producer.publish.call_args.args[0]

        assert event.event_type == DocumentEventType.CREATED
        assert event.document_id == result.document.id
        assert event.event_version == 1
        assert event.url == result.document.url
        assert event.content_hash == result.document.content_hash

    finally:
        document = get_document_by_url(
            db=db,
            url=test_url,
        )

        if document is not None:
            db.delete(document)
            db.commit()

        db.close()

def test_pipeline_publishes_updated_event_with_new_version():
    db = SessionLocal()

    test_url = "https://example.com/kafka-updated"

    try:
        event_producer = Mock()

        first_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Original</title>
        </head>
        <body>
            <p>Python programming language.</p>
        </body>
        </html>
        """

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = first_html
            mock_get.return_value.raise_for_status.return_value = None

            first_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                event_producer=event_producer,
            )

        first_result = first_results[0]

        assert first_result.change_type == DocumentChangeType.CREATED
        assert first_result.document.version == 1

        first_event = event_producer.publish.call_args.args[0]

        assert first_event.event_type == DocumentEventType.CREATED
        assert first_event.event_version == 1

        event_producer.reset_mock()

        second_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Updated</title>
        </head>
        <body>
            <p>Distributed systems search engine.</p>
        </body>
        </html>
        """

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = second_html
            mock_get.return_value.raise_for_status.return_value = None

            second_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                event_producer=event_producer,
            )

        second_result = second_results[0]

        assert second_result.change_type == DocumentChangeType.UPDATED
        assert second_result.document.version == 2
        assert second_result.document.id == first_result.document.id

        event_producer.publish.assert_called_once()

        second_event = event_producer.publish.call_args.args[0]

        assert second_event.event_type == DocumentEventType.UPDATED
        assert second_event.document_id == second_result.document.id
        assert second_event.event_version == 2
        assert second_event.url == second_result.document.url
        assert second_event.content_hash == second_result.document.content_hash

    finally:
        document = get_document_by_url(
            db=db,
            url=test_url,
        )

        if document is not None:
            db.delete(document)
            db.commit()

        db.close()

def test_pipeline_does_not_publish_event_for_unchanged_document():
    db = SessionLocal()

    test_url = "https://example.com/kafka-unchanged"

    try:
        event_producer = Mock()

        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            first_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                event_producer=event_producer,
            )

        first_result = first_results[0]

        assert first_result.change_type == DocumentChangeType.CREATED
        assert first_result.document.version == 1

        assert event_producer.publish.call_count == 1

        event_producer.reset_mock()

        # Crawl the exact same content again.
        with patch(
            "services.crawler.crawler.requests.get"
        ) as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = MOCK_HTML
            mock_get.return_value.raise_for_status.return_value = None

            second_results = crawl_and_store(
                db=db,
                start_url=test_url,
                max_pages=1,
                event_producer=event_producer,
            )

        second_result = second_results[0]

        assert second_result.change_type == DocumentChangeType.UNCHANGED
        assert second_result.document.version == 1

        # No Kafka event should be produced for unchanged content.
        event_producer.publish.assert_not_called()

    finally:
        document = get_document_by_url(
            db=db,
            url=test_url,
        )

        if document is not None:
            db.delete(document)
            db.commit()

        db.close()