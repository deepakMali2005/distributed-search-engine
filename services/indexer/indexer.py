from sqlalchemy.orm import Session

from services.indexer.analyzer import TextAnalyzer
from services.indexer.index import InvertedIndex
from services.storage.storage import get_all_documents


class Indexer:
    """
    Coordinates document retrieval, text analysis,
    and inverted-index construction.

    Responsibilities:
        PostgreSQL Documents
            ↓
        TextAnalyzer
            ↓
        InvertedIndex
    """

    def __init__(
        self,
        analyzer: TextAnalyzer | None = None,
        index: InvertedIndex | None = None,
    ) -> None:
        self.analyzer = analyzer or TextAnalyzer()
        self.index = index or InvertedIndex()

    def index_document(
        self,
        document_id: int,
        content: str,
    ) -> None:
        """
        Analyze and index a single document.
        """

        tokens = self.analyzer.analyze(content)

        self.index.add_document(
            doc_id=document_id,
            tokens=tokens,
        )

    def index_all_documents(
        self,
        db: Session,
    ) -> None:
        """
        Index all documents currently stored in PostgreSQL.
        """

        documents = get_all_documents(db)

        for document in documents:
            self.index_document(
                document_id=document.id,
                content=document.content,
            )

    def remove_document(
        self,
        document_id: int,
    ) -> None:
        """
        Remove a document from the inverted index.
        """

        self.index.remove_document(document_id)

    def get_index(self) -> InvertedIndex:
        """
        Return the underlying inverted index.
        """

        return self.index