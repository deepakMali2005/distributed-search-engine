import json
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from services.indexer.remote_shard_client import (
    HttpShardIndexClient,
    ShardIndexError,
)


def make_response(status=200):
    response = Mock()
    response.status = status
    response.read.return_value = b"{}"
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


def test_index_document_sends_expected_http_request():
    client = HttpShardIndexClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8101",
    )

    response = make_response()

    with patch(
        "services.indexer.remote_shard_client.urlopen",
        return_value=response,
    ) as urlopen:
        client.index_document(
            document_id=486,
            tokens=[
                "distribut",
                "search",
            ],
        )

    request = urlopen.call_args.args[0]

    assert request.method == "POST"
    assert request.full_url == (
        "http://127.0.0.1:8101/documents"
    )

    payload = json.loads(
        request.data.decode("utf-8")
    )

    assert payload == {
        "document_id": 486,
        "tokens": [
            "distribut",
            "search",
        ],
    }


def test_index_document_connection_failure_is_retryable():
    client = HttpShardIndexClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8101",
    )

    with patch(
        "services.indexer.remote_shard_client.urlopen",
        side_effect=URLError("connection refused"),
    ):
        with pytest.raises(
            ShardIndexError,
        ) as exc_info:
            client.index_document(
                document_id=486,
                tokens=["search"],
            )

    assert exc_info.value.retryable is True


def test_index_document_server_error_is_retryable():
    client = HttpShardIndexClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8101",
    )

    error = HTTPError(
        url="http://127.0.0.1:8101/documents",
        code=503,
        msg="Service unavailable",
        hdrs=None,
        fp=None,
    )

    with patch(
        "services.indexer.remote_shard_client.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            ShardIndexError,
        ) as exc_info:
            client.index_document(
                document_id=486,
                tokens=["search"],
            )

    assert exc_info.value.retryable is True


def test_index_document_client_error_is_not_retryable():
    client = HttpShardIndexClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8101",
    )

    error = HTTPError(
        url="http://127.0.0.1:8101/documents",
        code=400,
        msg="Bad request",
        hdrs=None,
        fp=None,
    )

    with patch(
        "services.indexer.remote_shard_client.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            ShardIndexError,
        ) as exc_info:
            client.index_document(
                document_id=486,
                tokens=["search"],
            )

    assert exc_info.value.retryable is False


def test_delete_document_accepts_not_found_as_idempotent():
    client = HttpShardIndexClient(
        shard_id="shard-1",
        base_url="http://127.0.0.1:8101",
    )

    error = HTTPError(
        url="http://127.0.0.1:8101/documents/486",
        code=404,
        msg="Not found",
        hdrs=None,
        fp=None,
    )

    with patch(
        "services.indexer.remote_shard_client.urlopen",
        side_effect=error,
    ):
        client.delete_document(
            document_id=486
        )