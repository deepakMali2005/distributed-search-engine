from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.indexer.shard_lifecycle import ShardLifecycleState


@dataclass(frozen=True)
class ShardManifest:
    """Durable metadata describing the currently published shard snapshot."""

    FORMAT_VERSION = 1

    shard_id: str
    generation: int
    state: ShardLifecycleState
    active_segments: tuple[str, ...]
    document_count: int

    def __post_init__(self) -> None:
        if not self.shard_id:
            raise ValueError("shard_id cannot be empty.")

        if self.generation < 0:
            raise ValueError("generation cannot be negative.")

        if self.document_count < 0:
            raise ValueError("document_count cannot be negative.")

        if not self.active_segments:
            raise ValueError("At least one active segment is required.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.FORMAT_VERSION,
            "shard_id": self.shard_id,
            "generation": self.generation,
            "state": self.state.value,
            "active_segments": list(self.active_segments),
            "document_count": self.document_count,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ShardManifest":
        if not isinstance(payload, dict):
            raise ValueError(
                "Invalid shard manifest: expected an object."
            )

        if payload.get("format_version") != cls.FORMAT_VERSION:
            raise ValueError(
                "Unsupported shard manifest format version."
            )

        shard_id = payload.get("shard_id")
        generation = payload.get("generation")
        state = payload.get("state")
        active_segments = payload.get("active_segments")
        document_count = payload.get("document_count")

        if not isinstance(shard_id, str) or not shard_id:
            raise ValueError(
                "Invalid shard manifest: shard_id is missing."
            )

        if not isinstance(generation, int) or generation < 0:
            raise ValueError(
                "Invalid shard manifest: generation."
            )

        if not isinstance(state, str):
            raise ValueError(
                "Invalid shard manifest: state."
            )

        try:
            lifecycle_state = ShardLifecycleState(state)
        except ValueError as exc:
            raise ValueError(
                "Invalid shard manifest: state."
            ) from exc

        if not isinstance(active_segments, list) or not active_segments:
            raise ValueError(
                "Invalid shard manifest: active_segments."
            )

        if not all(
            isinstance(segment, str) and segment
            for segment in active_segments
        ):
            raise ValueError(
                "Invalid shard manifest: active_segments."
            )

        if not isinstance(document_count, int) or document_count < 0:
            raise ValueError(
                "Invalid shard manifest: document_count."
            )

        return cls(
            shard_id=shard_id,
            generation=generation,
            state=lifecycle_state,
            active_segments=tuple(active_segments),
            document_count=document_count,
        )