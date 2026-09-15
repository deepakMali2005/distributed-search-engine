from dataclasses import dataclass, field

from services.indexer.index import InvertedIndex
from services.indexer.shard_lifecycle import ShardLifecycleState
from services.search.engine import SearchEngine
from services.search.models import SearchResult
from services.semantic.models import Embedding, SemanticSearchResult
from services.semantic.vector_index import VectorIndex


@dataclass
class Shard:
    shard_id: str
    index: InvertedIndex
    vector_index: VectorIndex = field(default_factory=VectorIndex)

    _lifecycle_state: ShardLifecycleState = field(
        default=ShardLifecycleState.NEW,
        init=False,
    )

    def __post_init__(self) -> None:
        if not self.shard_id:
            raise ValueError("shard_id cannot be empty.")

    @property
    def document_count(self) -> int:
        return self.index.document_count

    @property
    def lifecycle_state(self) -> ShardLifecycleState:
        return self._lifecycle_state

    def set_lifecycle_state(self, state: ShardLifecycleState) -> None:
        self._lifecycle_state = state

    def add_document(
        self,
        doc_id: int,
        tokens: list[str],
        embedding: Embedding | None = None,
    ) -> None:
        self.index.add_document(
            doc_id=doc_id,
            tokens=tokens,
        )

        if embedding is not None:
            self.vector_index.add_document(
                doc_id=doc_id,
                embedding=embedding,
            )
        else:
            # Never retain a stale semantic representation after a
            # lexical-only replacement of the same document.
            self.vector_index.remove_document(doc_id)

    def remove_document(self, doc_id: int) -> None:
        self.index.remove_document(doc_id)
        self.vector_index.remove_document(doc_id)

    def contains_document(self, doc_id: int) -> bool:
        return doc_id in self.index.document_ids

    def semantic_search(
        self,
        query_embedding: Embedding,
        limit: int = 10,
    ) -> list[SemanticSearchResult]:
        """Return the top semantic matches owned by this shard."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero.")

        return self.vector_index.search(
            query_embedding=query_embedding,
            top_k=limit,
        )

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero.")

        return SearchEngine(self.index).search(
            query=query,
            limit=limit,
        )