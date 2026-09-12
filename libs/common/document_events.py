from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class DocumentChangeType(str, Enum):
    """
    Describes what happened to a document during ingestion/storage.
    """

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class DocumentEventType(str, Enum):
    """
    Describes a document change that should be processed
    by the distributed indexing pipeline.
    """

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass(frozen=True)
class DocumentChangeEvent:
    """
    Durable event representing a change to a document.

    This is the contract exchanged between the document storage layer
    and the distributed indexing pipeline.

    The event intentionally does not contain the full document content.
    Consumers can use document_id to retrieve the current document from
    PostgreSQL, which remains the canonical source of truth.
    """

    event_id: str
    event_version: int
    event_type: DocumentEventType

    document_id: int
    url: str

    content_hash: str | None

    occurred_at: datetime

    metadata: dict[str, Any] = field(default_factory=dict)

    CURRENT_VERSION = 1

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """
        Validate the event contract.
        """

        if not self.event_id:
            raise ValueError("event_id must not be empty")

        if self.event_version < 1:
            raise ValueError("event_version must be >= 1")

        if not isinstance(self.event_type, DocumentEventType):
            raise ValueError(
                "event_type must be a DocumentEventType"
            )

        if self.document_id <= 0:
            raise ValueError(
                "document_id must be greater than 0"
            )

        if not self.url:
            raise ValueError("url must not be empty")

        if self.event_type != DocumentEventType.DELETED:
            if not self.content_hash:
                raise ValueError(
                    "content_hash is required for non-delete events"
                )

        if self.occurred_at.tzinfo is None:
            raise ValueError(
                "occurred_at must be timezone-aware"
            )

        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")

    @classmethod
    def create(
        cls,
        *,
        event_type: DocumentEventType,
        document_id: int,
        url: str,
        content_hash: str | None,
        event_version: int = 1,
        occurred_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "DocumentChangeEvent":
        """
        Create a new document change event.

        event_id is generated automatically.
        """

        if occurred_at is None:
            occurred_at = datetime.now(timezone.utc)

        return cls(
            event_id=str(uuid4()),
            event_version=event_version,
            event_type=event_type,
            document_id=document_id,
            url=url,
            content_hash=content_hash,
            occurred_at=occurred_at,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the event into a JSON-compatible dictionary.
        """

        return {
            "event_id": self.event_id,
            "event_version": self.event_version,
            "event_type": self.event_type.value,
            "document_id": self.document_id,
            "url": self.url,
            "content_hash": self.content_hash,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """
        Serialize the event to JSON.

        This is the representation that can later be sent to Kafka.
        """

        return json.dumps(
            self.to_dict(),
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "DocumentChangeEvent":
        """
        Reconstruct an event from a dictionary.
        """

        required_fields = {
            "event_id",
            "event_version",
            "event_type",
            "document_id",
            "url",
            "content_hash",
            "occurred_at",
            "metadata",
        }

        missing_fields = required_fields - data.keys()

        if missing_fields:
            raise ValueError(
                f"Missing required event fields: "
                f"{sorted(missing_fields)}"
            )

        try:
            event_type = DocumentEventType(
                data["event_type"]
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid event_type: {data['event_type']}"
            ) from exc

        try:
            occurred_at = datetime.fromisoformat(
                data["occurred_at"]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "occurred_at must be a valid ISO-8601 datetime"
            ) from exc

        return cls(
            event_id=data["event_id"],
            event_version=data["event_version"],
            event_type=event_type,
            document_id=data["document_id"],
            url=data["url"],
            content_hash=data["content_hash"],
            occurred_at=occurred_at,
            metadata=dict(data["metadata"]),
        )

    @classmethod
    def from_json(
        cls,
        payload: str,
    ) -> "DocumentChangeEvent":
        """
        Deserialize an event from JSON.
        """

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid event JSON"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                "Event JSON must contain an object"
            )

        return cls.from_dict(data)