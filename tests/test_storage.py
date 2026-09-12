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

def test_new_document_starts_at_version_one():
    db = SessionLocal()

    url = "https://example.com/version-created"

    try:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        document, change_type = save_document(
            db=db,
            url=url,
            title="Version Test",
            content="Initial content",
            content_type="text/html",
        )

        assert change_type.value == "created"
        assert document.version == 1

    finally:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        db.close()


def test_updated_document_increments_version():
    db = SessionLocal()

    url = "https://example.com/version-updated"

    try:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        document, change_type = save_document(
            db=db,
            url=url,
            title="Version Test",
            content="Initial content",
            content_type="text/html",
        )

        assert change_type.value == "created"
        assert document.version == 1

        updated_document, change_type = save_document(
            db=db,
            url=url,
            title="Version Test Updated",
            content="Updated content",
            content_type="text/html",
        )

        assert change_type.value == "updated"
        assert updated_document.id == document.id
        assert updated_document.version == 2

        updated_document, change_type = save_document(
            db=db,
            url=url,
            title="Version Test Updated Again",
            content="Third version",
            content_type="text/html",
        )

        assert change_type.value == "updated"
        assert updated_document.version == 3

    finally:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        db.close()


def test_unchanged_document_keeps_version():
    db = SessionLocal()

    url = "https://example.com/version-unchanged"

    try:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        document, change_type = save_document(
            db=db,
            url=url,
            title="Version Test",
            content="Same content",
            content_type="text/html",
        )

        assert change_type.value == "created"
        assert document.version == 1

        unchanged_document, change_type = save_document(
            db=db,
            url=url,
            title="Version Test",
            content="Same content",
            content_type="text/html",
        )

        assert change_type.value == "unchanged"
        assert unchanged_document.id == document.id
        assert unchanged_document.version == 1

    finally:
        existing = get_document_by_url(db, url)

        if existing is not None:
            db.delete(existing)
            db.commit()

        db.close()