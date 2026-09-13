from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from libs.common.document_events import DocumentChangeEvent
from libs.models import ProcessedEvent


def is_event_processed(
    db: Session,
    event_id: str,
) -> bool:
    """
    Check whether an event has already been successfully processed.
    """

    processed_event = db.get(
        ProcessedEvent,
        event_id,
    )

    return processed_event is not None


def record_processed_event(
    db: Session,
    event: DocumentChangeEvent,
) -> bool:
    """
    Record an event as successfully processed.

    Returns:
        True:
            The event was newly recorded.

        False:
            The event was already recorded.

    PostgreSQL's ON CONFLICT DO NOTHING guarantees that
    duplicate event IDs are handled safely.

    RETURNING is used instead of relying on rowcount because
    rowcount is not a reliable way to determine whether the
    INSERT actually created a row in this SQLAlchemy/PostgreSQL
    combination.
    """

    statement = (
        insert(ProcessedEvent)
        .values(
            event_id=event.event_id,
            document_id=event.document_id,
            event_version=event.event_version,
        )
        .on_conflict_do_nothing(
            index_elements=[
                ProcessedEvent.event_id,
            ]
        )
        .returning(
            ProcessedEvent.event_id,
        )
    )

    result = db.execute(statement)

    inserted_event_id = result.scalar_one_or_none()

    db.commit()

    return inserted_event_id is not None