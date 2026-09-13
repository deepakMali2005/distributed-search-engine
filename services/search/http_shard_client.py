from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from services.search.models import SearchResult


class HttpShardSearchClient:
    """
    HTTP client for a remote shard service.

    Implements the ShardSearchClient protocol used by
    SearchCoordinator.

    The coordinator does not know whether the shard is local
    or remote. It only depends on the search(query, limit)
    interface.
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

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        """
        Search the remote shard over HTTP.
        """
        if not query.strip():
            return []

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        encoded_query = quote(
            query,
            safe="",
        )

        url = (
            f"{self.base_url}/search"
            f"?q={encoded_query}"
            f"&limit={limit}"
        )

        request = Request(
            url,
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
                    raise RuntimeError(
                        f"Shard {self.shard_id} returned "
                        f"HTTP {response.status}."
                    )

                payload = json.loads(
                    response.read().decode("utf-8")
                )

        except HTTPError as exc:
            raise RuntimeError(
                f"Shard {self.shard_id} returned "
                f"HTTP {exc.code}."
            ) from exc

        except URLError as exc:
            raise RuntimeError(
                f"Shard {self.shard_id} is unavailable."
            ) from exc

        except TimeoutError as exc:
            raise RuntimeError(
                f"Shard {self.shard_id} timed out."
            ) from exc

        results = payload.get(
            "results",
            [],
        )

        return [
            SearchResult(
                doc_id=result["doc_id"],
                score=result["score"],
            )
            for result in results
        ]