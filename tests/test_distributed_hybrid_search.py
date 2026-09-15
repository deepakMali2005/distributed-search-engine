from __future__ import annotations

import time

import pytest

from services.search.candidates import DistributedCandidatePolicy
from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import ShardSearchError
from services.search.models import SearchResult
from services.semantic.models import Embedding


class FakeEmbeddingModel:
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> Embedding:
        self.calls.append(text)

        return Embedding(
            [1.0, 0.0, 0.0]
        )


class FakeHybridShard:
    def __init__(
        self,
        shard_id: str,
        lexical_results: list[SearchResult],
        semantic_results: list[SearchResult],
    ) -> None:
        self.shard_id = shard_id
        self.lexical_results = lexical_results
        self.semantic_results = semantic_results
        self.semantic_embeddings: list[Embedding] = []

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        return self.lexical_results[:limit]

    def semantic_search(
        self,
        query_embedding: Embedding,
        limit: int,
    ) -> list[SearchResult]:
        self.semantic_embeddings.append(
            query_embedding
        )

        return self.semantic_results[:limit]


def test_coordinator_combines_lexical_and_semantic_results_across_shards():
    shards = [
        FakeHybridShard(
            "shard-1",
            lexical_results=[
                SearchResult(
                    doc_id=1,
                    score=10.0,
                ),
                SearchResult(
                    doc_id=2,
                    score=5.0,
                ),
            ],
            semantic_results=[
                SearchResult(
                    doc_id=2,
                    score=0.95,
                ),
                SearchResult(
                    doc_id=3,
                    score=0.80,
                ),
            ],
        ),
        FakeHybridShard(
            "shard-2",
            lexical_results=[
                SearchResult(
                    doc_id=4,
                    score=8.0,
                ),
            ],
            semantic_results=[
                SearchResult(
                    doc_id=1,
                    score=0.90,
                ),
                SearchResult(
                    doc_id=4,
                    score=0.70,
                ),
            ],
        ),
    ]

    model = FakeEmbeddingModel()

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=model,
    )

    response = coordinator.hybrid_search(
        "python search",
        limit=4,
    )

    assert response.total_shards == 2
    assert response.successful_shards == 2
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0
    assert response.is_partial is False

    assert [
        result.doc_id
        for result in response.results
    ] == [1, 2, 4, 3]

    assert model.calls == [
        "python search"
    ]

    for shard in shards:
        assert len(
            shard.semantic_embeddings
        ) == 1

        assert (
            shard.semantic_embeddings[0].values
            == (1.0, 0.0, 0.0)
        )


def test_hybrid_search_respects_global_limit():
    shards = [
        FakeHybridShard(
            "shard-1",
            lexical_results=[
                SearchResult(
                    doc_id=1,
                    score=5.0,
                ),
                SearchResult(
                    doc_id=2,
                    score=4.0,
                ),
            ],
            semantic_results=[
                SearchResult(
                    doc_id=1,
                    score=0.9,
                ),
                SearchResult(
                    doc_id=2,
                    score=0.8,
                ),
            ],
        ),
        FakeHybridShard(
            "shard-2",
            lexical_results=[
                SearchResult(
                    doc_id=3,
                    score=3.0,
                ),
                SearchResult(
                    doc_id=4,
                    score=2.0,
                ),
            ],
            semantic_results=[
                SearchResult(
                    doc_id=3,
                    score=0.7,
                ),
                SearchResult(
                    doc_id=4,
                    score=0.6,
                ),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
    )

    response = coordinator.hybrid_search(
        "python",
        limit=2,
    )

    assert len(response.results) == 2

    assert [
        result.doc_id
        for result in response.results
    ] == [1, 2]


def test_hybrid_search_requires_embedding_model():
    coordinator = SearchCoordinator(
        shard_clients=[
            FakeHybridShard(
                "shard-1",
                [],
                [],
            ),
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="embedding_model",
    ):
        coordinator.hybrid_search(
            "python"
        )


def test_hybrid_search_empty_query_does_not_embed():
    model = FakeEmbeddingModel()

    coordinator = SearchCoordinator(
        shard_clients=[
            FakeHybridShard(
                "shard-1",
                [],
                [],
            ),
        ],
        embedding_model=model,
    )

    response = coordinator.hybrid_search(
        "   "
    )

    assert response.results == []

    assert response.total_shards == 1

    assert model.calls == []


def test_hybrid_search_partial_failure_keeps_successful_source_results():
    class SemanticFailingShard(
        FakeHybridShard
    ):
        def semantic_search(
            self,
            query_embedding: Embedding,
            limit: int,
        ) -> list[SearchResult]:
            raise RuntimeError(
                "semantic shard unavailable"
            )

    shards = [
        FakeHybridShard(
            "shard-1",
            lexical_results=[
                SearchResult(
                    doc_id=1,
                    score=5.0,
                ),
            ],
            semantic_results=[
                SearchResult(
                    doc_id=1,
                    score=0.9,
                ),
            ],
        ),
        SemanticFailingShard(
            "shard-2",
            lexical_results=[
                SearchResult(
                    doc_id=2,
                    score=4.0,
                ),
            ],
            semantic_results=[],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
        allow_partial_results=True,
    )

    response = coordinator.hybrid_search(
        "python",
        limit=10,
    )

    assert response.total_shards == 2
    assert response.successful_shards == 1
    assert response.failed_shards == 1
    assert response.timed_out_shards == 0
    assert response.is_partial is True

    assert {
        result.doc_id
        for result in response.results
    } == {1, 2}


def test_hybrid_search_strict_mode_rejects_failure_in_either_source():
    class LexicalFailingShard(
        FakeHybridShard
    ):
        def search(
            self,
            query: str,
            limit: int,
        ) -> list[SearchResult]:
            raise ShardSearchError(
                "temporary lexical failure",
                retryable=False,
            )

    coordinator = SearchCoordinator(
        shard_clients=[
            LexicalFailingShard(
                "shard-1",
                lexical_results=[],
                semantic_results=[
                    SearchResult(
                        doc_id=1,
                        score=0.9,
                    ),
                ],
            ),
        ],
        embedding_model=FakeEmbeddingModel(),
        allow_partial_results=False,
    )

    with pytest.raises(
        RuntimeError,
        match="one or more shards",
    ):
        coordinator.hybrid_search(
            "python"
        )


def test_hybrid_search_timeout_is_counted_once_per_shard():
    class SlowSemanticShard(
        FakeHybridShard
    ):
        def semantic_search(
            self,
            query_embedding: Embedding,
            limit: int,
        ) -> list[SearchResult]:
            time.sleep(0.2)

            return []

    coordinator = SearchCoordinator(
        shard_clients=[
            SlowSemanticShard(
                "shard-1",
                lexical_results=[
                    SearchResult(
                        doc_id=1,
                        score=5.0,
                    ),
                ],
                semantic_results=[],
            ),
            FakeHybridShard(
                "shard-2",
                lexical_results=[],
                semantic_results=[],
            ),
        ],
        embedding_model=FakeEmbeddingModel(),
        shard_timeout_seconds=0.05,
        allow_partial_results=True,
    )

    response = coordinator.hybrid_search(
        "python"
    )

    assert response.total_shards == 2
    assert response.timed_out_shards == 1
    assert response.failed_shards == 0
    assert response.successful_shards == 1
    assert response.is_partial is True

    assert [
        result.doc_id
        for result in response.results
    ] == [1]


def test_hybrid_search_retries_transient_semantic_failure():
    class TransientSemanticShard(
        FakeHybridShard
    ):
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            super().__init__(
                *args,
                **kwargs,
            )

            self.attempts = 0

        def semantic_search(
            self,
            query_embedding: Embedding,
            limit: int,
        ) -> list[SearchResult]:
            self.attempts += 1

            if self.attempts == 1:
                raise ShardSearchError(
                    "temporary semantic failure",
                    retryable=True,
                )

            return super().semantic_search(
                query_embedding,
                limit,
            )

    shard = TransientSemanticShard(
        "shard-1",
        lexical_results=[
            SearchResult(
                doc_id=1,
                score=5.0,
            ),
        ],
        semantic_results=[
            SearchResult(
                doc_id=1,
                score=0.9,
            ),
        ],
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        embedding_model=FakeEmbeddingModel(),
        max_retries=1,
        retry_backoff_seconds=0,
    )

    response = coordinator.hybrid_search(
        "python"
    )

    assert response.successful_shards == 1
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0
    assert response.results[0].doc_id == 1
    assert shard.attempts == 2


def test_hybrid_search_retries_transient_lexical_failure():
    class TransientLexicalShard(
        FakeHybridShard
    ):
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            super().__init__(
                *args,
                **kwargs,
            )

            self.attempts = 0

        def search(
            self,
            query: str,
            limit: int,
        ) -> list[SearchResult]:
            self.attempts += 1

            if self.attempts == 1:
                raise ShardSearchError(
                    "temporary lexical failure",
                    retryable=True,
                )

            return super().search(
                query,
                limit,
            )

    shard = TransientLexicalShard(
        "shard-1",
        lexical_results=[
            SearchResult(
                doc_id=1,
                score=5.0,
            ),
        ],
        semantic_results=[
            SearchResult(
                doc_id=1,
                score=0.9,
            ),
        ],
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        embedding_model=FakeEmbeddingModel(),
        max_retries=1,
        retry_backoff_seconds=0,
    )

    response = coordinator.hybrid_search(
        "python"
    )

    assert response.successful_shards == 1
    assert response.failed_shards == 0
    assert response.timed_out_shards == 0
    assert response.results[0].doc_id == 1
    assert shard.attempts == 2


def test_hybrid_search_expands_per_shard_candidate_window():
    class RecordingShard(FakeHybridShard):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lexical_limits: list[int] = []
            self.semantic_limits: list[int] = []

        def search(
            self,
            query: str,
            limit: int,
        ) -> list[SearchResult]:
            self.lexical_limits.append(limit)
            return super().search(query, limit)

        def semantic_search(
            self,
            query_embedding: Embedding,
            limit: int,
        ) -> list[SearchResult]:
            self.semantic_limits.append(limit)
            return super().semantic_search(query_embedding, limit)

    shards = [
        RecordingShard(
            "shard-1",
            lexical_results=[],
            semantic_results=[],
        ),
        RecordingShard(
            "shard-2",
            lexical_results=[],
            semantic_results=[],
        ),
    ]

    policy = DistributedCandidatePolicy(
        oversampling_factor=5,
        minimum_candidates=10,
    )

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
        candidate_policy=policy,
    )

    response = coordinator.hybrid_search(
        "python",
        limit=2,
    )

    assert response.results == []

    for shard in shards:
        assert shard.lexical_limits == [10]
        assert shard.semantic_limits == [10]


def test_hybrid_search_candidate_window_can_include_results_outside_final_k():
    shard = FakeHybridShard(
        "shard-1",
        lexical_results=[
            SearchResult(doc_id=1, score=10.0),
            SearchResult(doc_id=2, score=9.0),
            SearchResult(doc_id=3, score=2.0),
        ],
        semantic_results=[
            SearchResult(doc_id=3, score=0.99),
            SearchResult(doc_id=1, score=0.10),
            SearchResult(doc_id=2, score=0.05),
        ],
    )

    policy = DistributedCandidatePolicy(
        oversampling_factor=1,
        minimum_candidates=3,
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        embedding_model=FakeEmbeddingModel(),
        candidate_policy=policy,
    )

    response = coordinator.hybrid_search(
        "python",
        limit=2,
    )

    assert len(response.results) == 2

    assert [
        result.doc_id
        for result in response.results
    ] == [1, 3]


def test_hybrid_search_default_candidate_policy_is_used():
    class RecordingShard(FakeHybridShard):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lexical_limit: int | None = None
            self.semantic_limit: int | None = None

        def search(
            self,
            query: str,
            limit: int,
        ) -> list[SearchResult]:
            self.lexical_limit = limit
            return []

        def semantic_search(
            self,
            query_embedding: Embedding,
            limit: int,
        ) -> list[SearchResult]:
            self.semantic_limit = limit
            return []

    shard = RecordingShard(
        "shard-1",
        lexical_results=[],
        semantic_results=[],
    )

    coordinator = SearchCoordinator(
        shard_clients=[shard],
        embedding_model=FakeEmbeddingModel(),
    )

    coordinator.hybrid_search(
        "python",
        limit=10,
    )

    assert shard.lexical_limit == 50
    assert shard.semantic_limit == 50
