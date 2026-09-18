from __future__ import annotations

import threading

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.indexer.shard_persistence import JsonShardPersistence
from services.semantic.models import (
    Embedding,
    SemanticSearchResult,
)


class PersistentShardService:
    """
    Owns one shard and its durable persistence.

    The service loads the latest published shard generation
    during startup and persists successful mutations.
    """

    def __init__(
        self,
        shard: Shard,
        persistence: JsonShardPersistence,
    ) -> None:
        self.shard = shard
        self.persistence = persistence
        self._mutation_lock = threading.RLock()

    @classmethod
    def create(
        cls,
        shard_id: str,
        data_path: str,
    ) -> "PersistentShardService":
        shard = Shard(
            shard_id=shard_id,
            index=InvertedIndex(),
        )

        persistence = JsonShardPersistence(
            root_directory=data_path,
        )

        service = cls(
            shard=shard,
            persistence=persistence,
        )

        service.load()

        return service

    def load(self) -> bool:
        return self.persistence.load(
            self.shard
        )

    def index_document(
        self,
        document_id: int,
        tokens: list[str],
        embedding: Embedding | None = None,
    ) -> None:
        """
        Index one document and persist the new shard generation.
        """

        with self._mutation_lock:
            self.shard.add_document(
                doc_id=document_id,
                tokens=tokens,
                embedding=embedding,
            )

            self.persistence.save(
                self.shard
            )

    def index_documents(
        self,
        documents: list[
            tuple[int, list[str], Embedding | None]
        ],
    ) -> None:
        """
        Index multiple already-analyzed documents and publish one
        durable shard generation for the complete batch.

        This method is used by bootstrap/reconciliation.

        The normal Kafka worker continues to use index_document(),
        preserving the existing event-driven runtime behavior.
        """

        if not documents:
            raise ValueError(
                "documents cannot be empty."
            )

        document_ids = [
            document_id
            for document_id, _, _ in documents
        ]

        if len(document_ids) != len(
            set(document_ids)
        ):
            raise ValueError(
                "documents cannot contain duplicate document IDs."
            )

        with self._mutation_lock:
            for (
                document_id,
                tokens,
                embedding,
            ) in documents:
                self.shard.add_document(
                    doc_id=document_id,
                    tokens=tokens,
                    embedding=embedding,
                )

            # One persistence publication for the whole batch.
            self.persistence.save(
                self.shard
            )

    def delete_document(
        self,
        document_id: int,
    ) -> None:
        """
        Delete a document and persist the updated shard.
        """

        with self._mutation_lock:
            self.shard.remove_document(
                document_id
            )

            self.persistence.save(
                self.shard
            )

    def semantic_search(
        self,
        query_embedding: Embedding,
        limit: int,
    ) -> list[SemanticSearchResult]:
        return self.shard.semantic_search(
            query_embedding=query_embedding,
            limit=limit,
        )

    def search(
        self,
        query: str,
        limit: int,
    ):
        return self.shard.search(
            query=query,
            limit=limit,
        )

    def contains_document(
        self,
        document_id: int,
    ) -> bool:
        return self.shard.contains_document(
            document_id
        )

    @property
    def shard_id(self) -> str:
        return self.shard.shard_id

    @property
    def document_count(self) -> int:
        return self.shard.document_count

    @property
    def lifecycle_state(self):
        return self.shard.lifecycle_state