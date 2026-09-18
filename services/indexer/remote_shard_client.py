from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.semantic.models import Embedding


class ShardIndexError(RuntimeError):
    """
    Error raised when a remote shard indexing operation fails.

    retryable indicates whether retrying the operation may reasonably
    succeed.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable


class HttpShardIndexClient:
    """
    HTTP client used by indexer workers and bootstrap to mutate
    a remote shard.

    The worker is responsible for:
        - document retrieval
        - text analysis
        - embedding generation
        - consistent-hash routing

    The shard service is responsible for:
        - maintaining its local inverted index
        - maintaining its vector index
        - persistence
        - shard lifecycle
    """

    def __init__(
        self,
        shard_id: str,
        base_url: str,
        *,
        timeout_seconds: float = 2.0,
    ) -> None:
        if not shard_id:
            raise ValueError(
                "shard_id cannot be empty."
            )

        if not base_url:
            raise ValueError(
                "base_url cannot be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self.shard_id = shard_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def index_document(
        self,
        document_id: int,
        tokens: list[str],
        embedding: Embedding | None = None,
    ) -> None:
        """
        Index one already-analyzed document on the remote shard.
        """

        payload_data = {
            "document_id": document_id,
            "tokens": tokens,
        }

        if embedding is not None:
            payload_data["embedding"] = list(
                embedding.values
            )

        payload = json.dumps(
            payload_data
        ).encode("utf-8")

        request = Request(
            f"{self.base_url}/documents",
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                if response.status != 200:
                    raise ShardIndexError(
                        (
                            f"Shard {self.shard_id} "
                            f"returned HTTP {response.status} "
                            "while indexing."
                        ),
                        retryable=response.status >= 500,
                    )

                response.read()

        except HTTPError as exc:
            raise ShardIndexError(
                (
                    f"Shard {self.shard_id} "
                    f"returned HTTP {exc.code} "
                    "while indexing."
                ),
                retryable=exc.code >= 500,
            ) from exc

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise ShardIndexError(
                f"Shard {self.shard_id} is unavailable.",
                retryable=True,
            ) from exc

    def index_documents(
        self,
        documents: list[
            tuple[int, list[str], Embedding | None]
        ],
    ) -> None:
        """
        Index a bounded batch using one HTTP request.

        The shard persists the complete batch as one new immutable
        generation instead of persisting every document individually.
        """

        if not documents:
            raise ValueError(
                "documents cannot be empty."
            )

        document_ids = [
            document_id
            for document_id, _, _ in documents
        ]

        if len(document_ids) != len(
            set(document_ids)
        ):
            raise ValueError(
                "documents cannot contain duplicate document IDs."
            )

        payload = json.dumps(
            {
                "documents": [
                    {
                        "document_id": document_id,
                        "tokens": tokens,
                        **(
                            {
                                "embedding": list(
                                    embedding.values
                                )
                            }
                            if embedding is not None
                            else {}
                        ),
                    }
                    for document_id, tokens, embedding
                    in documents
                ]
            }
        ).encode("utf-8")

        request = Request(
            f"{self.base_url}/documents/bulk",
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                if response.status != 200:
                    raise ShardIndexError(
                        (
                            f"Shard {self.shard_id} "
                            f"returned HTTP {response.status} "
                            "while bulk indexing."
                        ),
                        retryable=response.status >= 500,
                    )

                response.read()

        except HTTPError as exc:
            raise ShardIndexError(
                (
                    f"Shard {self.shard_id} "
                    f"returned HTTP {exc.code} "
                    "while bulk indexing."
                ),
                retryable=exc.code >= 500,
            ) from exc

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise ShardIndexError(
                (
                    f"Shard {self.shard_id} "
                    "is unavailable during bulk indexing."
                ),
                retryable=True,
            ) from exc

    def delete_document(
        self,
        document_id: int,
    ) -> None:
        """
        Delete a document from the remote shard.
        """

        request = Request(
            f"{self.base_url}/documents/{document_id}",
            method="DELETE",
            headers={
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                if response.status != 200:
                    raise ShardIndexError(
                        (
                            f"Shard {self.shard_id} "
                            f"returned HTTP {response.status} "
                            "while deleting."
                        ),
                        retryable=response.status >= 500,
                    )

                response.read()

        except HTTPError as exc:
            if exc.code == 404:
                return

            raise ShardIndexError(
                (
                    f"Shard {self.shard_id} "
                    f"returned HTTP {exc.code} "
                    "while deleting."
                ),
                retryable=exc.code >= 500,
            ) from exc

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise ShardIndexError(
                f"Shard {self.shard_id} is unavailable.",
                retryable=True,
            ) from exc

    def contains_document(
        self,
        document_id: int,
    ) -> bool:
        """
        Check whether the remote shard currently contains
        the document.
        """

        request = Request(
            f"{self.base_url}/documents/{document_id}",
            method="GET",
            headers={
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                if response.status != 200:
                    return False

                response.read()

                return True

        except HTTPError as exc:
            if exc.code == 404:
                return False

            raise ShardIndexError(
                (
                    f"Shard {self.shard_id} "
                    f"returned HTTP {exc.code} "
                    "while checking document."
                ),
                retryable=exc.code >= 500,
            ) from exc

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise ShardIndexError(
                f"Shard {self.shard_id} is unavailable.",
                retryable=True,
            ) from exc