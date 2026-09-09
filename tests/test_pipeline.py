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

from services.pipeline.pipeline import crawl_and_store
from services.search_api.database import SessionLocal
from services.storage.storage import get_document_by_url


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

        document = documents[0]

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
