from enum import Enum


class DocumentChangeType(str, Enum):
    """
    Describes what happened to a document during ingestion.
    """

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"