from enum import Enum


class EventVersionState(str, Enum):
    DUPLICATE = "duplicate"
    STALE = "stale"
    CURRENT = "current"
    FUTURE = "future"


def classify_event_version(
    event_version: int,
    latest_indexed_version: int | None,
    document_version: int,
) -> EventVersionState:
    """
    Classify a document event according to its relationship with
    the search index and canonical PostgreSQL document.

    Rules:

    - latest indexed >= event version:
        The event is already represented by the search index.

    - document version > event version:
        PostgreSQL contains a newer document version, so the event
        is stale.

    - document version == event version:
        The event represents the current canonical document version.

    - document version < event version:
        The event is ahead of PostgreSQL and must be retried.
    """

    if (
        latest_indexed_version is not None
        and event_version <= latest_indexed_version
    ):
        return EventVersionState.STALE

    if document_version > event_version:
        return EventVersionState.STALE

    if document_version < event_version:
        return EventVersionState.FUTURE

    return EventVersionState.CURRENT