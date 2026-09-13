from datetime import datetime, timezone

from services.search_api.database import SessionLocal
from services.storage.document_index_versions import (
    get_latest_indexed_version,
    record_indexed_version,
)
from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.models import DocumentIndexVersion


DOCUMENT_ID = 999991


def make_event(
    *,
    version: int,
    event_id: str,
) -> DocumentChangeEvent:
    return DocumentChangeEvent(
        event_id=event_id,
        event_version=version,
        event_type=DocumentEventType.UPDATED,
        document_id=DOCUMENT_ID,
        url="https://example.com/version-test",
        content_hash=f"hash-v{version}",
        occurred_at=datetime(
            2026,
            9,
            13,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        metadata={},
    )


def cleanup(db) -> None:
    existing = db.get(
        DocumentIndexVersion,
        DOCUMENT_ID,
    )

    if existing is not None:
        db.delete(existing)
        db.commit()


def test_latest_indexed_version_is_none_before_recording():
    db = SessionLocal()

    try:
        cleanup(db)

        assert (
            get_latest_indexed_version(
                db=db,
                document_id=DOCUMENT_ID,
            )
            is None
        )

    finally:
        cleanup(db)
        db.close()


def test_record_indexed_version_stores_version():
    db = SessionLocal()

    try:
        cleanup(db)

        event = make_event(
            version=1,
            event_id="00000000-0000-0000-0000-000000000001",
        )

        inserted = record_indexed_version(
            db=db,
            event=event,
        )

        assert inserted is True

        assert (
            get_latest_indexed_version(
                db=db,
                document_id=DOCUMENT_ID,
            )
            == 1
        )

    finally:
        cleanup(db)
        db.close()


def test_newer_version_replaces_previous_version():
    db = SessionLocal()

    try:
        cleanup(db)

        event_v1 = make_event(
            version=1,
            event_id="00000000-0000-0000-0000-000000000001",
        )

        event_v2 = make_event(
            version=2,
            event_id="00000000-0000-0000-0000-000000000002",
        )

        assert record_indexed_version(
            db=db,
            event=event_v1,
        )

        assert record_indexed_version(
            db=db,
            event=event_v2,
        )

        assert (
            get_latest_indexed_version(
                db=db,
                document_id=DOCUMENT_ID,
            )
            == 2
        )

    finally:
        cleanup(db)
        db.close()


def test_older_version_cannot_replace_newer_version():
    db = SessionLocal()

    try:
        cleanup(db)

        event_v2 = make_event(
            version=2,
            event_id="00000000-0000-0000-0000-000000000002",
        )

        event_v1 = make_event(
            version=1,
            event_id="00000000-0000-0000-0000-000000000001",
        )

        assert record_indexed_version(
            db=db,
            event=event_v2,
        )

        inserted = record_indexed_version(
            db=db,
            event=event_v1,
        )

        assert inserted is False

        assert (
            get_latest_indexed_version(
                db=db,
                document_id=DOCUMENT_ID,
            )
            == 2
        )

    finally:
        cleanup(db)
        db.close()


def test_same_version_cannot_replace_existing_version():
    db = SessionLocal()

    try:
        cleanup(db)

        event_v1_a = make_event(
            version=1,
            event_id="00000000-0000-0000-0000-000000000001",
        )

        event_v1_b = make_event(
            version=1,
            event_id="00000000-0000-0000-0000-000000000002",
        )

        assert record_indexed_version(
            db=db,
            event=event_v1_a,
        )

        inserted = record_indexed_version(
            db=db,
            event=event_v1_b,
        )

        assert inserted is False

        assert (
            get_latest_indexed_version(
                db=db,
                document_id=DOCUMENT_ID,
            )
            == 1
        )

    finally:
        cleanup(db)
        db.close()