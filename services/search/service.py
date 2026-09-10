from sqlalchemy.orm import Session

from services.indexer.indexer import Indexer
from services.search.engine import SearchEngine
from services.search.models import SearchResult


class SearchService:
    """
    Application-level service that prepares the search index
    and executes searches.

    PostgreSQL
        ↓
    Indexer
        ↓
    InvertedIndex
        ↓
    SearchEngine
    """

    def __init__(self) -> None:
        self.indexer = Indexer()
        self.engine = SearchEngine(
            self.indexer.get_index()
        )

        self._initialized = False

    def initialize(self, db: Session) -> None:
        """
        Load all stored documents into the in-memory index.
        """

        self.indexer.index_all_documents(db)
        self._initialized = True

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Execute a search against the loaded index.
        """

        if not self._initialized:
            raise RuntimeError(
                "SearchService has not been initialized."
            )

        return self.engine.search(
            query=query,
            limit=limit,
        )