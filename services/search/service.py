from sqlalchemy.orm import Session

from services.indexer.indexer import Indexer
from services.indexer.persistence import JsonIndexPersistence
from services.search.engine import SearchEngine
from services.search.models import SearchResult


class SearchService:
    """
    Coordinates the persistent index and search engine.
    """

    def __init__(
        self,
        index_path: str = "data/index/index.json",
    ) -> None:
        self.indexer = Indexer(
            persistence=JsonIndexPersistence(
                index_path
            )
        )

        self.engine = SearchEngine(
            self.indexer.get_index()
        )

        self._initialized = False

    def initialize(
        self,
        db: Session,
    ) -> None:
        """
        Initialize the search index.

        If a persistent index exists, load it.

        Otherwise build the index from PostgreSQL
        and persist it.
        """

        loaded = self.indexer.load()

        if not loaded:
            self.indexer.index_all_documents(db)

        self.engine = SearchEngine(
            self.indexer.get_index()
        )

        self._initialized = True

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        if not self._initialized:
            raise RuntimeError(
                "SearchService has not been initialized."
            )

        return self.engine.search(
            query=query,
            limit=limit,
        )