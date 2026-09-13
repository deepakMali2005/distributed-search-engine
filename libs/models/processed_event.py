from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProcessedEvent(Base):
    """
    Durable record of successfully processed document events.

    event_id is the unique identity of a Kafka document event.
    """

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    document_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    event_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )