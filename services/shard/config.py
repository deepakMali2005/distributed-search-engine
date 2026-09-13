from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ShardServiceConfig:
    """
    Runtime configuration for an independent shard service.
    """

    shard_id: str
    host: str
    port: int
    data_path: str

    @classmethod
    def from_environment(cls) -> "ShardServiceConfig":
        shard_id = os.getenv(
            "SHARD_ID",
            "shard-0",
        )

        host = os.getenv(
            "SHARD_HOST",
            "0.0.0.0",
        )

        port = int(
            os.getenv(
                "SHARD_PORT",
                "8001",
            )
        )

        data_path = os.getenv(
            "SHARD_DATA_PATH",
            "data/index/shards",
        )

        if not shard_id:
            raise ValueError(
                "SHARD_ID cannot be empty"
            )

        if port <= 0 or port > 65535:
            raise ValueError(
                "SHARD_PORT must be between 1 and 65535"
            )

        if not data_path:
            raise ValueError(
                "SHARD_DATA_PATH cannot be empty"
            )

        return cls(
            shard_id=shard_id,
            host=host,
            port=port,
            data_path=data_path,
        )