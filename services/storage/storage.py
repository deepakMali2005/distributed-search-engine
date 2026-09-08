from sqlalchemy.orm import Session

from libs.models import Document


def save_document(
    db: Session,
    url: str,
    content: str,
    title: str | None = None,
    content_type: str | None = None,
) -> Document:
    document = Document(
        url=url,
        title=title,
        content=content,
        content_type=content_type,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_document(
    db: Session,
    document_id: int,
) -> Document | None:
    return db.get(Document, document_id)


def get_document_by_url(
    db: Session,
    url: str,
) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.url == url)
        .first()
    )


def get_all_documents(
    db: Session,
) -> list[Document]:
    return db.query(Document).all()