from __future__ import annotations

import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from services.search.http_shard_client import (
    HttpShardSearchClient,
    ShardSearchError,
)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def read(self):
        return json.dumps(
            {
                "shard_id": "shard-1",
                "results": [
                    {
                        "doc_id": 10,
                        "score": 4.5,
                    },
                    {
                        "doc_id": 20,
                        "score": 2.5,
                    },
                ],
            }
        ).encode("utf-8")


def test_http_client_search_returns_results():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    with patch(
        "services.search.http_shard_client.urlopen",
        return_value=FakeResponse(),
    ) as mock_urlopen:
        results = client.search(
            query="distributed search",
            limit=10,
        )

    assert len(results) == 2

    assert results[0].doc_id == 10
    assert results[0].score == 4.5

    assert results[1].doc_id == 20
    assert results[1].score == 2.5

    request = mock_urlopen.call_args.args[0]

    assert (
        request.full_url
        == "http://127.0.0.1:8001/search"
        "?q=distributed%20search&limit=10"
    )


def test_http_client_rejects_invalid_limit():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    with pytest.raises(ValueError):
        client.search(
            query="python",
            limit=0,
        )


def test_http_client_empty_query_returns_empty():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    results = client.search(
        query="   ",
        limit=10,
    )

    assert results == []


def test_http_client_rejects_empty_shard_id():
    with pytest.raises(ValueError):
        HttpShardSearchClient(
            shard_id="",
            base_url="http://127.0.0.1:8001",
        )


def test_http_client_rejects_empty_base_url():
    with pytest.raises(ValueError):
        HttpShardSearchClient(
            shard_id="shard-1",
            base_url="",
        )


def test_http_client_rejects_invalid_timeout():
    with pytest.raises(ValueError):
        HttpShardSearchClient(
            shard_id="shard-1",
            base_url="http://127.0.0.1:8001",
            timeout_seconds=0,
        )


def test_http_client_retries_are_classified_as_retryable():
    error = ShardSearchError(
        "temporary failure",
        retryable=True,
    )

    assert error.retryable is True


def test_http_client_permanent_errors_are_not_retryable():
    error = ShardSearchError(
        "permanent failure",
        retryable=False,
    )

    assert error.retryable is False


def test_http_client_http_500_is_retryable():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    error = HTTPError(
        url="http://127.0.0.1:8001/search",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )

    with patch(
        "services.search.http_shard_client.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            ShardSearchError,
        ) as exc_info:
            client.search(
                query="python",
                limit=10,
            )

    assert exc_info.value.retryable is True


def test_http_client_http_404_is_not_retryable():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    error = HTTPError(
        url="http://127.0.0.1:8001/search",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None,
    )

    with patch(
        "services.search.http_shard_client.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            ShardSearchError,
        ) as exc_info:
            client.search(
                query="python",
                limit=10,
            )

    assert exc_info.value.retryable is False


def test_http_client_network_error_is_retryable():
    client = HttpShardSearchClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8001",
    )

    error = URLError(
        "connection refused"
    )

    with patch(
        "services.search.http_shard_client.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            ShardSearchError,
        ) as exc_info:
            client.search(
                query="python",
                limit=10,
            )

    assert exc_info.value.retryable is True