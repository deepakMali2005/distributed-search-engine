from __future__ import annotations

from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from typing import Protocol

from services.indexer.shard import Shard
from services.indexer.shard_manager import ShardManager
from services.search.models import SearchResult


class ShardSearchClient(Protocol):
    """
    Interface used by the coordinator to search a shard.

    Both local Shards and remote HTTP clients implement
    this interface.
    """

    shard_id: str

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        ...


@dataclass(frozen=True)
class ShardSearchOutcome:
    """
    Result of searching one shard.
    """

    shard_id: str
    results: list[SearchResult]
    error: str | None = None
    timed_out: bool = False

    @property
    def successful(self) -> bool:
        return (
            self.error is None
            and not self.timed_out
        )


@dataclass(frozen=True)
class SearchResponse:
    """
    Final response returned by the distributed search coordinator.
    """

    results: list[SearchResult]

    total_shards: int
    successful_shards: int
    failed_shards: int
    timed_out_shards: int

    @property
    def is_partial(self) -> bool:
        return (
            self.failed_shards > 0
            or self.timed_out_shards > 0
        )


class SearchCoordinator:
    """
    Coordinates searches across multiple shards.

    The coordinator can operate against either:

    1. A local ShardManager.
    2. A collection of remote ShardSearchClient instances.

    This keeps the search coordination layer independent
    from the transport mechanism.
    """

    def __init__(
        self,
        shard_manager: ShardManager | None = None,
        *,
        shard_clients: list[ShardSearchClient] | None = None,
        shard_timeout_seconds: float = 2.0,
        allow_partial_results: bool = True,
    ) -> None:
        if shard_timeout_seconds <= 0:
            raise ValueError(
                "shard_timeout_seconds must be greater than zero."
            )

        if (
            shard_manager is None
            and not shard_clients
        ):
            raise ValueError(
                "Provide either shard_manager "
                "or shard_clients."
            )

        if (
            shard_manager is not None
            and shard_clients is not None
        ):
            raise ValueError(
                "Provide either shard_manager "
                "or shard_clients, not both."
            )

        self.shard_manager = shard_manager
        self.shard_clients = shard_clients

        self.shard_timeout_seconds = (
            shard_timeout_seconds
        )

        self.allow_partial_results = (
            allow_partial_results
        )

    @property
    def shard_count(self) -> int:
        """
        Return the number of shards participating in search.
        """
        if self.shard_clients is not None:
            return len(self.shard_clients)

        if self.shard_manager is not None:
            return self.shard_manager.shard_count

        return 0

    def _get_shards(
        self,
    ) -> list[ShardSearchClient]:
        """
        Return the configured shard search clients.
        """
        if self.shard_clients is not None:
            return list(self.shard_clients)

        if self.shard_manager is not None:
            return self.shard_manager.get_all_shards()

        return []

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> SearchResponse:
        """
        Execute a distributed search across all shards.
        """
        if not query.strip():
            return SearchResponse(
                results=[],
                total_shards=self.shard_count,
                successful_shards=0,
                failed_shards=0,
                timed_out_shards=0,
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        shards = self._get_shards()

        if not shards:
            return SearchResponse(
                results=[],
                total_shards=0,
                successful_shards=0,
                failed_shards=0,
                timed_out_shards=0,
            )

        outcomes = self._search_shards(
            shards=shards,
            query=query,
            limit=limit,
        )

        failed_shards = sum(
            1
            for outcome in outcomes
            if outcome.error is not None
            and not outcome.timed_out
        )

        timed_out_shards = sum(
            1
            for outcome in outcomes
            if outcome.timed_out
        )

        successful_shards = sum(
            1
            for outcome in outcomes
            if outcome.successful
        )

        if (
            not self.allow_partial_results
            and (
                failed_shards > 0
                or timed_out_shards > 0
            )
        ):
            raise RuntimeError(
                "Search failed because one or more shards "
                "were unavailable."
            )

        merged_results = self._merge_results(
            outcomes=outcomes,
            limit=limit,
        )

        return SearchResponse(
            results=merged_results,
            total_shards=len(shards),
            successful_shards=successful_shards,
            failed_shards=failed_shards,
            timed_out_shards=timed_out_shards,
        )

    def _search_shards(
        self,
        shards: list[ShardSearchClient],
        query: str,
        limit: int,
    ) -> list[ShardSearchOutcome]:
        """
        Search all shards concurrently.
        """
        executor = ThreadPoolExecutor(
            max_workers=len(shards),
            thread_name_prefix="search-shard",
        )

        futures: dict[
            Future[list[SearchResult]],
            ShardSearchClient,
        ] = {}

        try:
            for shard in shards:
                future = executor.submit(
                    shard.search,
                    query,
                    limit,
                )

                futures[future] = shard

            done, not_done = wait(
                futures,
                timeout=self.shard_timeout_seconds,
            )

            outcomes: list[ShardSearchOutcome] = []

            for future in done:
                shard = futures[future]

                try:
                    results = future.result()

                    outcomes.append(
                        ShardSearchOutcome(
                            shard_id=shard.shard_id,
                            results=results,
                        )
                    )

                except Exception as exc:
                    outcomes.append(
                        ShardSearchOutcome(
                            shard_id=shard.shard_id,
                            results=[],
                            error=str(exc),
                        )
                    )

            for future in not_done:
                shard = futures[future]

                future.cancel()

                outcomes.append(
                    ShardSearchOutcome(
                        shard_id=shard.shard_id,
                        results=[],
                        timed_out=True,
                    )
                )

            return outcomes

        finally:
            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

    @staticmethod
    def _merge_results(
        outcomes: list[ShardSearchOutcome],
        limit: int,
    ) -> list[SearchResult]:
        """
        Merge shard results into one globally ranked result list.

        If the same document appears on multiple shards, the
        highest score is retained.
        """
        best_scores: dict[int, float] = {}

        for outcome in outcomes:
            if not outcome.successful:
                continue

            for result in outcome.results:
                existing_score = best_scores.get(
                    result.doc_id
                )

                if (
                    existing_score is None
                    or result.score > existing_score
                ):
                    best_scores[result.doc_id] = (
                        result.score
                    )

        ranked_results = sorted(
            best_scores.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )

        return [
            SearchResult(
                doc_id=doc_id,
                score=score,
            )
            for doc_id, score in ranked_results[:limit]
        ]