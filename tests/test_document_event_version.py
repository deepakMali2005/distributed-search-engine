from libs.common.document_event_version import (
    EventVersionState,
    classify_event_version,
)


def test_current_version():
    state = classify_event_version(
        event_version=2,
        latest_indexed_version=1,
        document_version=2,
    )

    assert state == EventVersionState.CURRENT


def test_stale_against_index():
    state = classify_event_version(
        event_version=1,
        latest_indexed_version=2,
        document_version=2,
    )

    assert state == EventVersionState.STALE


def test_same_version_as_index_is_stale():
    state = classify_event_version(
        event_version=2,
        latest_indexed_version=2,
        document_version=2,
    )

    assert state == EventVersionState.STALE


def test_stale_against_database():
    state = classify_event_version(
        event_version=1,
        latest_indexed_version=None,
        document_version=2,
    )

    assert state == EventVersionState.STALE


def test_future_version():
    state = classify_event_version(
        event_version=3,
        latest_indexed_version=1,
        document_version=2,
    )

    assert state == EventVersionState.FUTURE


def test_first_event_is_current():
    state = classify_event_version(
        event_version=1,
        latest_indexed_version=None,
        document_version=1,
    )

    assert state == EventVersionState.CURRENT