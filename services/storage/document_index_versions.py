from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from libs.common.document_events import DocumentChangeEvent
from libs.models import DocumentIndexVersion


def get_latest_indexed_version(
    db: Session,
    document_id: int,
) -> int | None:
    record = db.get(DocumentIndexVersion, document_id)

    # Some callers/tests may use a Session mock that returns a different
    # model for db.get(). Treat that as "no indexed-version record".
    if not isinstance(record, DocumentIndexVersion):
        return None

    return record.event_version


def record_indexed_version(
    db: Session,
    event: DocumentChangeEvent,
) -> bool:
    statement = (
        insert(DocumentIndexVersion)
        .values(
            document_id=event.document_id,
            event_version=event.event_version,
            event_id=event.event_id,
        )
        .on_conflict_do_update(
            index_elements=[DocumentIndexVersion.document_id],
            set_={
                "event_version": event.event_version,
                "event_id": event.event_id,
                "indexed_at": DocumentIndexVersion.indexed_at,
            },
            where=(
                event.event_version
                > DocumentIndexVersion.event_version
            ),
        )
        .returning(DocumentIndexVersion.document_id)
    )

    result = db.execute(statement)
    document_id = result.scalar_one_or_none()

    db.commit()

    return document_id is not None
