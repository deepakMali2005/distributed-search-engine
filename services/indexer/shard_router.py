from bisect import bisect_right
import hashlib


class ShardRouter:
    """
    Routes documents to shards using consistent hashing.

    Documents and shards are placed on a hash ring.
    A document is assigned to the first shard encountered
    clockwise from the document's hash position.
    """

    def __init__(
        self,
        shard_ids: list[str],
        virtual_nodes: int = 100,
    ) -> None:
        if not shard_ids:
            raise ValueError(
                "At least one shard is required."
            )

        if virtual_nodes <= 0:
            raise ValueError(
                "virtual_nodes must be greater than zero."
            )

        if len(set(shard_ids)) != len(shard_ids):
            raise ValueError(
                "Shard IDs must be unique."
            )

        self.shard_ids = list(shard_ids)
        self.virtual_nodes = virtual_nodes

        self._ring: dict[int, str] = {}
        self._ring_positions: list[int] = []

        self._build_ring()

    def _hash(self, value: str) -> int:
        """
        Convert a value into a deterministic hash position.
        """

        digest = hashlib.sha256(
            value.encode("utf-8")
        ).digest()

        return int.from_bytes(
            digest,
            byteorder="big",
        )

    def _build_ring(self) -> None:
        """
        Build the consistent hash ring.
        """

        self._ring.clear()

        for shard_id in self.shard_ids:
            for replica in range(self.virtual_nodes):
                key = f"{shard_id}:{replica}"

                position = self._hash(key)

                self._ring[position] = shard_id

        self._ring_positions = sorted(
            self._ring
        )

    def get_shard_id(
        self,
        document_id: int,
    ) -> str:
        """
        Return the shard responsible for a document.
        """

        if not self._ring_positions:
            raise RuntimeError(
                "Hash ring is empty."
            )

        position = self._hash(
            str(document_id)
        )

        index = bisect_right(
            self._ring_positions,
            position,
        )

        # Wrap around the ring.
        if index == len(self._ring_positions):
            index = 0

        return self._ring[
            self._ring_positions[index]
        ]