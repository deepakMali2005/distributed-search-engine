"""
Real-world Kafka indexing smoke test.

Flow:

    PostgreSQL document update
        ↓
    Storage change detection
        ↓
    DocumentChangeEvent
        ↓
    Kafka
        ↓
    Indexer Worker
        ↓
    ShardManager
        ↓
    Persistent shard
"""

from libs.common.document_events import (
    DocumentChangeEvent,
    DocumentChangeType,
    DocumentEventType,
)
from services.events.producer import DocumentEventProducer
from services.search_api.database import SessionLocal
from services.storage.storage import get_document, save_document


DOCUMENT_ID = 486


def main():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("REAL-WORLD KAFKA INDEXING TEST")
        print("=" * 60)

        document = get_document(
            db=db,
            document_id=DOCUMENT_ID,
        )

        if document is None:
            raise RuntimeError(
                f"Document {DOCUMENT_ID} was not found."
            )

        print(f"Document ID      : {document.id}")
        print(f"Current version  : {document.version}")
        print(f"Title            : {document.title}")
        print(f"URL              : {document.url}")
        print()

        # Add a unique marker to force an UPDATE.
        marker = (
            " Distributed Search Engine Kafka smoke test "
            "event verification version three."
        )

        updated_content = document.content

        if marker not in updated_content:
            updated_content += marker

        saved_document, change_type = save_document(
            db=db,
            url=document.url,
            title=document.title,
            content=updated_content,
            content_type=document.content_type,
        )

        print(f"Storage result   : {change_type.value}")
        print(f"New version      : {saved_document.version}")
        print()

        if change_type != DocumentChangeType.UPDATED:
            raise RuntimeError(
                "Expected an UPDATED document, but storage returned "
                f"{change_type.value}."
            )

        # Convert the storage change into the production Kafka event.
        event = DocumentChangeEvent.create(
            event_type=DocumentEventType.UPDATED,
            document_id=saved_document.id,
            url=saved_document.url,
            content_hash=saved_document.content_hash,
            event_version=saved_document.version,
        )

        print("Kafka event:")
        print(f"  Event ID       : {event.event_id}")
        print(f"  Event type     : {event.event_type.value}")
        print(f"  Document ID    : {event.document_id}")
        print(f"  Event version  : {event.event_version}")
        print()

        producer = DocumentEventProducer()
        producer.publish(event)

        print("Kafka publish    : SUCCESS")
        print()
        print("The running Indexer Worker should now consume this event.")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()