import pytest
from pydantic import ValidationError

from services.search_api.models import (
    SearchMode,
    SearchResponse,
    SearchResultResponse,
)


def test_search_mode_contains_supported_modes():
    assert SearchMode.lexical.value == "lexical"
    assert SearchMode.semantic.value == "semantic"
    assert SearchMode.hybrid.value == "hybrid"


def test_search_result_response_contains_document_and_score():
    result = SearchResultResponse(
        doc_id=42,
        score=0.75,
    )

    assert result.doc_id == 42
    assert result.score == 0.75


def test_search_response_contains_distributed_metadata():
    response = SearchResponse(
        query="distributed systems",
        mode=SearchMode.hybrid,
        results=[
            SearchResultResponse(
                doc_id=42,
                score=0.91,
            )
        ],
        total_shards=3,
        successful_shards=3,
        failed_shards=0,
        timed_out_shards=0,
        partial=False,
    )

    assert response.query == "distributed systems"
    assert response.mode == SearchMode.hybrid
    assert response.results[0].doc_id == 42

    assert response.total_shards == 3
    assert response.successful_shards == 3
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0
    assert response.partial is False


def test_search_response_accepts_partial_distributed_results():
    response = SearchResponse(
        query="search",
        mode=SearchMode.hybrid,
        results=[],
        total_shards=3,
        successful_shards=2,
        failed_shards=1,
        timed_out_shards=0,
        partial=True,
    )

    assert response.partial is True
    assert response.successful_shards == 2
    assert response.failed_shards == 1


@pytest.mark.parametrize(
    "mode",
    [
        "lexical",
        "semantic",
        "hybrid",
    ],
)
def test_search_response_accepts_supported_modes(mode):
    response = SearchResponse(
        query="search",
        mode=mode,
        results=[],
        total_shards=1,
        successful_shards=1,
        failed_shards=0,
        timed_out_shards=0,
        partial=False,
    )

    assert response.mode.value == mode


def test_search_response_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        SearchResponse(
            query="search",
            mode="unknown",
            results=[],
            total_shards=1,
            successful_shards=1,
            failed_shards=0,
            timed_out_shards=0,
            partial=False,
        )


def test_search_response_rejects_negative_shard_counts():
    with pytest.raises(ValidationError):
        SearchResponse(
            query="search",
            mode=SearchMode.hybrid,
            results=[],
            total_shards=-1,
            successful_shards=0,
            failed_shards=0,
            timed_out_shards=0,
            partial=False,
        )