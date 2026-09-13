from datetime import datetime, timezone

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)
from libs.models import ProcessedEvent
from services.search_api.database import SessionLocal
from services.storage.processed_events import (
    is_event_processed,
    record_processed_event,
)


def make_event(
    *,
    event_id: str | None = None,
    document_id: int = 900001,
    event_version: int = 1,
) -> DocumentChangeEvent:
    kwargs = {
        "event_type": DocumentEventType.CREATED,
        "document_id": document_id,
        "url": "https://example.com/idempotency-test",
        "content_hash": "idempotency-test-hash",
        "event_version": event_version,
        "occurred_at": datetime.now(timezone.utc),
    }

    if event_id is not None:
        kwargs["event_id"] = event_id

    return DocumentChangeEvent.create(
        **kwargs
    )


def cleanup_event(
    db,
    event_id: str,
) -> None:
    existing = db.get(
        ProcessedEvent,
        event_id,
    )

    if existing is not None:
        db.delete(existing)
        db.commit()


def test_event_is_not_processed_before_recording():
    db = SessionLocal()
    event = make_event()

    try:
        cleanup_event(
            db,
            event.event_id,
        )

        assert (
            is_event_processed(
                db=db,
                event_id=event.event_id,
            )
            is False
        )

    finally:
        cleanup_event(
            db,
            event.event_id,
        )
        db.close()


def test_event_can_be_recorded():
    db = SessionLocal()
    event = make_event()

    try:
        cleanup_event(
            db,
            event.event_id,
        )

        result = record_processed_event(
            db=db,
            event=event,
        )

        assert result is True

        stored = db.get(
            ProcessedEvent,
            event.event_id,
        )

        assert stored is not None
        assert stored.event_id == event.event_id
        assert stored.document_id == event.document_id
        assert stored.event_version == event.event_version
        assert stored.processed_at is not None

        assert (
            is_event_processed(
                db=db,
                event_id=event.event_id,
            )
            is True
        )

    finally:
        cleanup_event(
            db,
            event.event_id,
        )
        db.close()


def test_recorded_event_is_detected_as_processed():
    db = SessionLocal()
    event = make_event()

    try:
        cleanup_event(
            db,
            event.event_id,
        )

        result = record_processed_event(
            db=db,
            event=event,
        )

        assert result is True

        assert (
            is_event_processed(
                db=db,
                event_id=event.event_id,
            )
            is True
        )

    finally:
        cleanup_event(
            db,
            event.event_id,
        )
        db.close()


def test_recording_same_event_twice_is_safe():
    db = SessionLocal()
    event = make_event()

    try:
        cleanup_event(
            db,
            event.event_id,
        )

        first_result = record_processed_event(
            db=db,
            event=event,
        )

        second_result = record_processed_event(
            db=db,
            event=event,
        )

        assert first_result is True
        assert second_result is False

        stored = db.get(
            ProcessedEvent,
            event.event_id,
        )

        assert stored is not None
        assert stored.event_id == event.event_id
        assert stored.document_id == event.document_id
        assert stored.event_version == event.event_version

    finally:
        cleanup_event(
            db,
            event.event_id,
        )
        db.close()


def test_different_event_ids_can_be_recorded():
    db = SessionLocal()

    event_one = make_event(
        document_id=900002,
        event_version=1,
    )

    event_two = make_event(
        document_id=900002,
        event_version=2,
    )

    try:
        cleanup_event(
            db,
            event_one.event_id,
        )

        cleanup_event(
            db,
            event_two.event_id,
        )

        first_result = record_processed_event(
            db=db,
            event=event_one,
        )

        second_result = record_processed_event(
            db=db,
            event=event_two,
        )

        assert first_result is True
        assert second_result is True

        assert is_event_processed(
            db=db,
            event_id=event_one.event_id,
        )

        assert is_event_processed(
            db=db,
            event_id=event_two.event_id,
        )

    finally:
        cleanup_event(
            db,
            event_one.event_id,
        )

        cleanup_event(
            db,
            event_two.event_id,
        )

        db.close()


def test_event_version_and_document_id_are_persisted():
    db = SessionLocal()

    event = make_event(
        document_id=900003,
        event_version=7,
    )

    try:
        cleanup_event(
            db,
            event.event_id,
        )

        result = record_processed_event(
            db=db,
            event=event,
        )

        assert result is True

        stored = db.get(
            ProcessedEvent,
            event.event_id,
        )

        assert stored is not None
        assert stored.document_id == 900003
        assert stored.event_version == 7

    finally:
        cleanup_event(
            db,
            event.event_id,
        )
        db.close()