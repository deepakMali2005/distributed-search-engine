from __future__ import annotations

from services.semantic.models import Embedding, SemanticSearchResult
from services.semantic.similarity import cosine_similarity


class VectorIndex:
    """
    In-memory vector index for semantic retrieval.

    The index stores one embedding per document ID and performs
    exact nearest-neighbor search using cosine similarity.

    This implementation intentionally favors correctness and
    simplicity over approximate-nearest-neighbor performance.
    The internal implementation can later be replaced without
    changing the public interface.
    """

    def __init__(self) -> None:
        self._embeddings: dict[int, Embedding] = {}

    def add_document(
        self,
        doc_id: int,
        embedding: Embedding,
    ) -> None:
        """
        Add or replace the embedding for a document.

        If the document already exists, its previous embedding
        is replaced.
        """

        if doc_id <= 0:
            raise ValueError(
                "doc_id must be greater than zero."
            )

        if self._embeddings:
            existing_dimension = self.dimension

            if embedding.dimension != existing_dimension:
                raise ValueError(
                    "Embedding dimension does not match the "
                    f"index dimension: {embedding.dimension} != "
                    f"{existing_dimension}."
                )

        self._embeddings[doc_id] = embedding

    def remove_document(
        self,
        doc_id: int,
    ) -> None:
        """
        Remove a document embedding from the index.

        Removing a document that does not exist is a no-op.
        """

        self._embeddings.pop(doc_id, None)

    def contains_document(
        self,
        doc_id: int,
    ) -> bool:
        """
        Return True if an embedding exists for the document.
        """

        return doc_id in self._embeddings

    def get_embedding(
        self,
        doc_id: int,
    ) -> Embedding | None:
        """
        Return the embedding for a document.

        None is returned when the document is not indexed.
        """

        return self._embeddings.get(doc_id)

    def search(
        self,
        query_embedding: Embedding,
        top_k: int = 10,
    ) -> list[SemanticSearchResult]:
        """
        Return the top-K documents ranked by cosine similarity.

        Results are ordered by:
            1. descending similarity score
            2. ascending document ID for deterministic tie-breaking
        """

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        if not self._embeddings:
            return []

        if query_embedding.dimension != self.dimension:
            raise ValueError(
                "Query embedding dimension does not match the "
                f"index dimension: {query_embedding.dimension} != "
                f"{self.dimension}."
            )

        results = [
            SemanticSearchResult(
                doc_id=doc_id,
                score=cosine_similarity(
                    query_embedding,
                    embedding,
                ),
            )
            for doc_id, embedding in self._embeddings.items()
        ]

        results.sort(
            key=lambda result: (
                -result.score,
                result.doc_id,
            )
        )

        return results[:top_k]

    def clear(self) -> None:
        """
        Remove all embeddings from the index.
        """

        self._embeddings.clear()

    @property
    def document_count(self) -> int:
        """
        Return the number of documents in the vector index.
        """

        return len(self._embeddings)

    @property
    def document_ids(self) -> set[int]:
        """
        Return all document IDs stored in the vector index.
        """

        return set(self._embeddings)

    @property
    def dimension(self) -> int:
        """
        Return the embedding dimension used by this index.

        Raises:
            ValueError: If the index contains no embeddings.
        """

        if not self._embeddings:
            raise ValueError(
                "Vector index has no embeddings."
            )

        first_embedding = next(
            iter(self._embeddings.values())
        )

        return first_embedding.dimension