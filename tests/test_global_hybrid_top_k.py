from __future__ import annotations

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
        return self.semantic_results[:limit]


def test_global_hybrid_top_k_deduplicates_documents_across_shards():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=1, score=10.0),
                SearchResult(doc_id=2, score=8.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.90),
                SearchResult(doc_id=3, score=0.80),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=1, score=7.0),
                SearchResult(doc_id=4, score=6.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.70),
                SearchResult(doc_id=4, score=0.60),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
    )

    response = coordinator.hybrid_search("search", limit=10)

    assert [result.doc_id for result in response.results] == [1, 3, 2, 4]
    assert len(response.results) == 4


def test_global_hybrid_top_k_keeps_semantic_only_candidates():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=1, score=10.0),
            ],
            semantic_results=[
                SearchResult(doc_id=2, score=0.95),
                SearchResult(doc_id=1, score=0.10),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
    )

    response = coordinator.hybrid_search("search", limit=2)

    assert [result.doc_id for result in response.results] == [1, 2]


def test_global_hybrid_top_k_applies_limit_after_global_fusion():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=1, score=10.0),
                SearchResult(doc_id=2, score=8.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.90),
                SearchResult(doc_id=2, score=0.80),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=3, score=9.0),
                SearchResult(doc_id=4, score=7.0),
            ],
            semantic_results=[
                SearchResult(doc_id=3, score=0.85),
                SearchResult(doc_id=4, score=0.70),
            ],
        ),
    ]

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
    )

    response = coordinator.hybrid_search("search", limit=2)

    assert len(response.results) == 2
    assert [result.doc_id for result in response.results] == [1, 3]


def test_global_hybrid_top_k_uses_highest_duplicate_score_per_source():
    shards = [
        FakeShard(
            "shard-1",
            lexical_results=[
                SearchResult(doc_id=1, score=5.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.20),
            ],
        ),
        FakeShard(
            "shard-2",
            lexical_results=[
                SearchResult(doc_id=1, score=10.0),
            ],
            semantic_results=[
                SearchResult(doc_id=1, score=0.90),
            ],
        ),
    ]

    ranker = HybridRanker(
        lexical_weight=0.5,
        semantic_weight=0.5,
    )

    coordinator = SearchCoordinator(
        shard_clients=shards,
        embedding_model=FakeEmbeddingModel(),
        hybrid_ranker=ranker,
    )

    response = coordinator.hybrid_search("search", limit=10)

    assert len(response.results) == 1
    assert response.results[0].doc_id == 1
    assert response.results[0].score == 1.0