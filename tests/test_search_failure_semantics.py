from __future__ import annotations

from services.search.coordinator import (
    SearchResponse,
    ShardSearchOutcome,
)
from services.search.models import SearchResult


def test_successful_search_is_not_partial():
    response = SearchResponse(
        results=[
            SearchResult(
                doc_id=1,
                score=5.0,
            )
        ],
        total_shards=3,
        successful_shards=3,
        failed_shards=0,
        timed_out_shards=0,
    )

    assert response.is_partial is False
    assert response.successful_shards == response.total_shards


def test_failed_shard_makes_search_partial():
    response = SearchResponse(
        results=[],
        total_shards=3,
        successful_shards=2,
        failed_shards=1,
        timed_out_shards=0,
    )

    assert response.is_partial is True


def test_timed_out_shard_makes_search_partial():
    response = SearchResponse(
        results=[],
        total_shards=3,
        successful_shards=2,
        failed_shards=0,
        timed_out_shards=1,
    )

    assert response.is_partial is True


def test_failed_and_timed_out_shards_are_both_partial():
    response = SearchResponse(
        results=[],
        total_shards=4,
        successful_shards=2,
        failed_shards=1,
        timed_out_shards=1,
    )

    assert response.is_partial is True
    assert (
        response.successful_shards
        + response.failed_shards
        + response.timed_out_shards
        == response.total_shards
    )


def test_successful_shard_outcome():
    outcome = ShardSearchOutcome(
        shard_id="shard-0",
        results=[
            SearchResult(
                doc_id=100,
                score=2.5,
            )
        ],
    )

    assert outcome.successful is True
    assert outcome.error is None
    assert outcome.timed_out is False


def test_failed_shard_outcome():
    outcome = ShardSearchOutcome(
        shard_id="shard-1",
        results=[],
        error="shard unavailable",
    )

    assert outcome.successful is False
    assert outcome.error == "shard unavailable"
    assert outcome.timed_out is False


def test_timed_out_shard_outcome():
    outcome = ShardSearchOutcome(
        shard_id="shard-2",
        results=[],
        timed_out=True,
    )

    assert outcome.successful is False
    assert outcome.error is None
    assert outcome.timed_out is True


def test_successful_shards_are_exactly_the_non_failed_non_timed_out_shards():
    outcomes = [
        ShardSearchOutcome(
            shard_id="shard-0",
            results=[],
        ),
        ShardSearchOutcome(
            shard_id="shard-1",
            results=[],
            error="connection refused",
        ),
        ShardSearchOutcome(
            shard_id="shard-2",
            results=[],
            timed_out=True,
        ),
        ShardSearchOutcome(
            shard_id="shard-3",
            results=[],
        ),
    ]

    successful = sum(
        outcome.successful
        for outcome in outcomes
    )

    failed = sum(
        outcome.error is not None
        and not outcome.timed_out
        for outcome in outcomes
    )

    timed_out = sum(
        outcome.timed_out
        for outcome in outcomes
    )

    assert successful == 2
    assert failed == 1
    assert timed_out == 1

    assert (
        successful + failed + timed_out
        == len(outcomes)
    )