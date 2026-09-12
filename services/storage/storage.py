import hashlib

from sqlalchemy.orm import Session

from libs.common.document_events import DocumentChangeType
from libs.models import Document


def calculate_content_hash(content: str) -> str:
    """
    Calculate a SHA-256 hash for document content.
    """

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def save_document(
    db: Session,
    url: str,
    content: str,
    title: str | None = None,
    content_type: str | None = None,
) -> tuple[Document, DocumentChangeType]:
    """
    Create a new document or update an existing document.

    Returns:
        The document and the type of change.

    CREATED:
        Document did not previously exist.
        The document starts at version 1.

    UPDATED:
        Document existed but its content changed.
        The document version is incremented.

    UNCHANGED:
        Document existed and its content did not change.
        The document version remains unchanged.
    """

    content_hash = calculate_content_hash(content)

    existing_document = get_document_by_url(
        db=db,
        url=url,
    )

    # New document.
    if existing_document is None:
        document = Document(
            url=url,
            title=title,
            content=content,
            content_type=content_type,
            content_hash=content_hash,
            version=1,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document, DocumentChangeType.CREATED

    # Existing document with identical content.
    if existing_document.content_hash == content_hash:
        return existing_document, DocumentChangeType.UNCHANGED

    # Existing document with changed content.
    existing_document.title = title
    existing_document.content = content
    existing_document.content_type = content_type
    existing_document.content_hash = content_hash
    existing_document.version += 1

    db.commit()
    db.refresh(existing_document)

    return existing_document, DocumentChangeType.UPDATED


def get_document(
    db: Session,
    document_id: int,
) -> Document | None:
    """
    Retrieve a document by ID.
    """

    return db.get(
        Document,
        document_id,
    )


def get_document_by_url(
    db: Session,
    url: str,
) -> Document | None:
    """
    Retrieve a document by URL.
    """

    return (
        db.query(Document)
        .filter(Document.url == url)
        .first()
    )


def get_all_documents(
    db: Session,
) -> list[Document]:
    """
    Retrieve all stored documents.
    """

    return db.query(Document).all()


def delete_document(
    db: Session,
    document_id: int,
) -> bool:
    """
    Delete a document by ID.

    Returns:
        True if the document existed and was deleted.
        False otherwise.
    """

    document = get_document(
        db=db,
        document_id=document_id,
    )

    if document is None:
        return False

    db.delete(document)
    db.commit()

    return True