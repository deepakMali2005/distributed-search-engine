from services.search_api.database import SessionLocal
from services.storage.storage import (
    save_document,
    get_document_by_url,
)


def test_document_storage():
    db = SessionLocal()

    url = "https://example.com/test-document"

    try:
        # Remove old test data if it exists
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        document = save_document(
            db=db,
            url=url,
            title="Test Document",
            content="This is a test document for our distributed search engine.",
            content_type="text/html",
        )

        found = get_document_by_url(db, url)

        assert found is not None
        assert found.url == url
        assert found.title == "Test Document"
        assert found.content == (
            "This is a test document for our distributed search engine."
        )

    finally:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        db.close()