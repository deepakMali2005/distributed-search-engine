from datetime import datetime, timezone

import pytest

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentEventType,
)


def test_create_event_generates_event_id():
    event = DocumentChangeEvent.create(
        event_type=DocumentEventType.CREATED,
        document_id=123,
        url="https://example.com",
        content_hash="abc123",
    )

    assert event.event_id
    assert event.event_version == 1
    assert event.event_type == DocumentEventType.CREATED
    assert event.document_id == 123
    assert event.url == "https://example.com"
    assert event.content_hash == "abc123"


def test_event_round_trip_json():
    occurred_at = datetime(
        2026,
        9,
        10,
        12,
        30,
        tzinfo=timezone.utc,
    )

    event = DocumentChangeEvent.create(
        event_type=DocumentEventType.UPDATED,
        document_id=42,
        url="https://example.com/page",
        content_hash="hash123",
        occurred_at=occurred_at,
        metadata={
            "source": "crawler",
        },
    )

    payload = event.to_json()
    restored = DocumentChangeEvent.from_json(payload)

    assert restored == event


def test_deleted_event_can_have_no_content_hash():
    event = DocumentChangeEvent.create(
        event_type=DocumentEventType.DELETED,
        document_id=99,
        url="https://example.com/deleted",
        content_hash=None,
    )

    assert event.event_type == DocumentEventType.DELETED
    assert event.content_hash is None


def test_non_delete_event_requires_content_hash():
    with pytest.raises(ValueError):
        DocumentChangeEvent.create(
            event_type=DocumentEventType.CREATED,
            document_id=1,
            url="https://example.com",
            content_hash=None,
        )


def test_document_id_must_be_positive():
    with pytest.raises(ValueError):
        DocumentChangeEvent.create(
            event_type=DocumentEventType.CREATED,
            document_id=0,
            url="https://example.com",
            content_hash="hash",
        )


def test_url_must_not_be_empty():
    with pytest.raises(ValueError):
        DocumentChangeEvent.create(
            event_type=DocumentEventType.CREATED,
            document_id=1,
            url="",
            content_hash="hash",
        )


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        DocumentChangeEvent.create(
            event_type=DocumentEventType.CREATED,
            document_id=1,
            url="https://example.com",
            content_hash="hash",
            occurred_at=datetime(2026, 9, 10),
        )


def test_invalid_event_type_is_rejected():
    with pytest.raises(ValueError):
        DocumentChangeEvent(
            event_id="event-1",
            event_version=1,
            event_type="invalid",
            document_id=1,
            url="https://example.com",
            content_hash="hash",
            occurred_at=datetime.now(timezone.utc),
        )


def test_missing_required_field_is_rejected():
    with pytest.raises(ValueError):
        DocumentChangeEvent.from_dict(
            {
                "event_id": "event-1",
            }
        )


def test_invalid_json_is_rejected():
    with pytest.raises(ValueError):
        DocumentChangeEvent.from_json(
            "not valid json"
        )