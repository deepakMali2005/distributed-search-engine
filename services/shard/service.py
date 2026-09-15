from __future__ import annotations

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.indexer.shard_persistence import (
    JsonShardPersistence,
)
from services.semantic.models import Embedding


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
        self.shard.add_document(
            doc_id=document_id,
            tokens=tokens,
            embedding=embedding,
        )

        self.persistence.save(
            self.shard
        )

    def delete_document(
        self,
        document_id: int,
    ) -> None:
        self.shard.remove_document(
            document_id
        )

        self.persistence.save(
            self.shard
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