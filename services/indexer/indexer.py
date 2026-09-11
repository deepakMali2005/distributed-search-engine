from sqlalchemy.orm import Session

from services.indexer.analyzer import TextAnalyzer
from services.indexer.index import InvertedIndex
from services.storage.storage import get_all_documents
from services.indexer.persistence import IndexPersistence


class Indexer:
    """
    Coordinates document retrieval, text analysis,
    inverted-index construction, and persistence.

    Responsibilities:

        PostgreSQL Documents
                ↓
          TextAnalyzer
                ↓
         InvertedIndex
                ↕
        IndexPersistence
    """

    def __init__(
        self,
        analyzer: TextAnalyzer | None = None,
        index: InvertedIndex | None = None,
        persistence: IndexPersistence | None = None,
    ) -> None:
        self.analyzer = analyzer or TextAnalyzer()
        self.index = index or InvertedIndex()
        self.persistence = persistence

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

        if self.persistence is not None:
            self.persistence.save(self.index)

    def index_all_documents(
        self,
        db: Session,
    ) -> None:
        """
        Build the index from all documents in PostgreSQL.

        Persistence happens once after the full indexing operation.
        """

        documents = get_all_documents(db)

        for document in documents:
            self.index_document_without_persist(
                document_id=document.id,
                content=document.content,
            )

        self.persist()

    def index_document_without_persist(
        self,
        document_id: int,
        content: str,
    ) -> None:
        """
        Index a document without immediately persisting.
        """

        tokens = self.analyzer.analyze(content)

        self.index.add_document(
            doc_id=document_id,
            tokens=tokens,
        )

    def remove_document(
        self,
        document_id: int,
    ) -> None:
        """
        Remove a document from the inverted index.
        """

        self.index.remove_document(document_id)

        self.persist()

    def persist(self) -> None:
        """
        Persist the current index if persistence is configured.
        """

        if self.persistence is not None:
            self.persistence.save(self.index)

    def load(self) -> bool:
        """
        Load the persistent index.

        Returns:
            True if an index was loaded.
            False if no persistent index exists.
        """

        if self.persistence is None:
            return False

        loaded_index = self.persistence.load()

        if loaded_index is None:
            return False

        self.index = loaded_index

        return True

    def get_index(self) -> InvertedIndex:
        """
        Return the underlying inverted index.
        """

        return self.index