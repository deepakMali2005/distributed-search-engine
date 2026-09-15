from __future__ import annotations

from services.search.candidates import DistributedCandidatePolicy
from services.search.coordinator import SearchCoordinator
from services.search.hybrid import HybridRanker
from services.search.models import SearchResult
from services.semantic.models import Embedding


class FakeEmbeddingModel:
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> Embedding:
        self.calls.append(text)
        return Embedding([1.0, 0.0, 0.0])


class FakeShard:
    def __init__(
        self,
        shard_id: str,
        lexical_results: list[SearchResult],
        semantic_results: list[SearchResult],
    ) -> None:
        self.shard_id = shard_id
        self.lexical_results = lexical_results
        self.semantic_results = semantic_results
        self.lexical_limits: list[int] = []
        self.semantic_limits: list[int] = []

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        self.lexical_limits.append(limit)
        return self.lexical_results[:limit]

    def semantic_search(
        self,
        query_embedding: Embedding,
        limit: int,
    ) -> list[SearchResult]:
        self.semantic_limits.append(limit)
        return self.semantic_results[:limit]


class FailingShard(FakeShard):
    def search(
        self,
        query: str,
        limit: int,
    ) -> list[SearchResult]:
        self.lexical_limits.append(limit)
        raise RuntimeError("lexical shard failure")

    def semantic_search(
        self,
        query_embedding: Embedding,
        limit: int,
    ) -> list[SearchResult]:
        self.semantic_limits.append(limit)
        raise RuntimeError("semantic shard failure")


def test_final_top_k_is_selected_after_global_hybrid_fusion():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=1, score=10.0),
                SearchResult(doc_id=2, score=8.0),
                SearchResult(doc_id=3, score=6.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.90),
                SearchResult(doc_id=2, score=0.80),
                SearchResult(doc_id=3, score=0.70),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=4, score=9.0),
                SearchResult(doc_id=5, score=7.0),
                SearchResult(doc_id=6, score=5.0),
            ],
            semantic_results=[
                SearchResult(doc_id=4, score=0.85),
                SearchResult(doc_id=5, score=0.75),
                SearchResult(doc_id=6, score=0.65),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
        candidate_policy=DistributedCandidatePolicy(
            oversampling_factor=3,
            minimum_candidates=3,
        ),
    )

    response = coordinator.hybrid_search(
        query="search",
        limit=3,
    )

    assert [
        result.doc_id
        for result in response.results
    ] == [1, 4, 2]

    assert len(response.results) == 3


def test_candidate_expansion_is_applied_to_every_shard_and_source():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=1, score=5.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.9),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=2, score=4.0),
            ],
            semantic_results=[
                SearchResult(doc_id=2, score=0.8),
            ],
        ),
        FakeShard(
            "shard-3",
            lexical_results=[
                SearchResult(doc_id=3, score=3.0),
            ],
            semantic_results=[
                SearchResult(doc_id=3, score=0.7),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
        candidate_policy=DistributedCandidatePolicy(
            oversampling_factor=4,
            minimum_candidates=10,
        ),
    )

    coordinator.hybrid_search(
        query="search",
        limit=2,
    )

    for shard in shards:
        assert shard.lexical_limits == [10]
        assert shard.semantic_limits == [10]


def test_final_top_k_deduplicates_candidates_before_returning_results():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=10, score=10.0),
                SearchResult(doc_id=11, score=8.0),
            ],
            semantic_results=[
                SearchResult(doc_id=10, score=0.9),
                SearchResult(doc_id=11, score=0.8),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=10, score=7.0),
                SearchResult(doc_id=12, score=6.0),
            ],
            semantic_results=[
                SearchResult(doc_id=10, score=0.7),
                SearchResult(doc_id=12, score=0.6),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
    )

    response = coordinator.hybrid_search(
        query="search",
        limit=10,
    )

    document_ids = [
        result.doc_id
        for result in response.results
    ]

    assert document_ids == [
        10,
        11,
        12,
    ]

    assert len(document_ids) == len(set(document_ids))


def test_partial_shard_failure_does_not_corrupt_global_top_k():
    healthy_shard = FakeShard(
        "healthy",
        lexical_results=[
            SearchResult(doc_id=20, score=10.0),
            SearchResult(doc_id=21, score=8.0),
        ],
        semantic_results=[
            SearchResult(doc_id=20, score=0.95),
            SearchResult(doc_id=21, score=0.80),
        ],
    )

    failing_shard = FailingShard(
        "failing",
        lexical_results=[],
        semantic_results=[],
    )

    coordinator = SearchCoordinator(
        shard_clients=[
            healthy_shard,
            failing_shard,
        ],
        embedding_model=FakeEmbeddingModel(),
        allow_partial_results=True,
    )

    response = coordinator.hybrid_search(
        query="search",
        limit=2,
    )

    assert response.total_shards == 2
    assert response.successful_shards == 1
    assert response.failed_shards == 1
    assert response.timed_out_shards == 0
    assert response.is_partial is True

    assert [
        result.doc_id
        for result in response.results
    ] == [20, 21]


def test_query_embedding_is_created_once_for_final_distributed_search():
    embedding_model = FakeEmbeddingModel()

    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=30, score=5.0),
            ],
            semantic_results=[
                SearchResult(doc_id=30, score=0.9),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=31, score=4.0),
            ],
            semantic_results=[
                SearchResult(doc_id=31, score=0.8),
            ],
        ),
        FakeShard(
            "shard-3",
            lexical_results=[
                SearchResult(doc_id=32, score=3.0),
            ],
            semantic_results=[
                SearchResult(doc_id=32, score=0.7),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=embedding_model,
    )

    coordinator.hybrid_search(
        query="distributed search",
        limit=3,
    )

    assert embedding_model.calls == [
        "distributed search"
    ]