from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DocumentIndexVersion(Base):
    __tablename__ = "document_index_versions"

    document_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )