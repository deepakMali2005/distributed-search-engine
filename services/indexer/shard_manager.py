from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.indexer.shard_persistence import (
    JsonShardPersistence,
)
from services.indexer.shard_router import ShardRouter


class ShardManager:
    """
    Owns shards, routing, and optional durable
    shard persistence.
    """

    def __init__(
        self,
        shard_ids: list[str],
        virtual_nodes: int = 100,
        persistence: JsonShardPersistence | None = None,
        auto_load: bool = False,
    ) -> None:
        if not shard_ids:
            raise ValueError(
                "At least one shard is required."
            )

        self.router = ShardRouter(
            shard_ids=shard_ids,
            virtual_nodes=virtual_nodes,
        )

        self.persistence = persistence

        self._shards = {
            shard_id: Shard(
                shard_id=shard_id,
                index=InvertedIndex(),
            )
            for shard_id in shard_ids
        }

        if auto_load:
            self.load()

    def get_shard(
        self,
        shard_id: str,
    ) -> Shard:
        if shard_id not in self._shards:
            raise KeyError(
                f"Unknown shard: {shard_id}"
            )

        return self._shards[shard_id]

    def get_shard_for_document(
        self,
        document_id: int,
    ) -> Shard:
        shard_id = self.router.get_shard_id(
            document_id
        )

        return self.get_shard(shard_id)

    def index_document(
        self,
        document_id: int,
        tokens: list[str],
    ) -> str:
        shard = self.get_shard_for_document(
            document_id
        )

        shard.add_document(
            document_id,
            tokens,
        )

        if self.persistence is not None:
            self.persistence.save(shard)

        return shard.shard_id

    def remove_document(
        self,
        document_id: int,
    ) -> str:
        shard = self.get_shard_for_document(
            document_id
        )

        shard.remove_document(
            document_id
        )

        if self.persistence is not None:
            self.persistence.save(shard)

        return shard.shard_id

    def persist(self) -> None:
        if self.persistence is None:
            return

        for shard in self.get_all_shards():
            self.persistence.save(shard)

    def load(self) -> dict[str, bool]:
        if self.persistence is None:
            return {
                shard.shard_id: False
                for shard in self.get_all_shards()
            }

        return {
            shard.shard_id: self.persistence.load(
                shard
            )
            for shard in self.get_all_shards()
        }

    def get_all_shards(self) -> list[Shard]:
        return list(
            self._shards.values()
        )

    @property
    def shard_count(self) -> int:
        return len(self._shards)