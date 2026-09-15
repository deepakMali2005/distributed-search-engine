import pytest

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.search.engine import SearchEngine
from services.semantic.models import Embedding


class FakeEmbeddingModel:
    def __init__(self, embeddings: dict[str, list[float]]) -> None:
        self._embeddings = embeddings
        self.calls: list[str] = []

    @property
    def dimension(self) -> int:
        return len(next(iter(self._embeddings.values())))

    def embed(self, text: str) -> Embedding:
        self.calls.append(text)
        return Embedding(self._embeddings[text])


def build_hybrid_shard() -> Shard:
    shard = Shard(
        shard_id="shard-001",
        index=InvertedIndex(),
    )

    shard.add_document(
        doc_id=1,
        tokens=["python", "search"],
        embedding=Embedding([1.0, 0.0]),
    )
    shard.add_document(
        doc_id=2,
        tokens=["database"],
        embedding=Embedding([0.0, 1.0]),
    )
    shard.add_document(
        doc_id=3,
        tokens=["python", "engine"],
        embedding=Embedding([0.8, 0.6]),
    )

    return shard


def test_hybrid_search_combines_lexical_and_semantic_results():
    shard = build_hybrid_shard()
    model = FakeEmbeddingModel({
        "python search": [1.0, 0.0],
    })

    results = shard.hybrid_search(
        query="python search",
        embedding_model=model,
        limit=10,
    )

    assert {result.doc_id for result in results} == {1, 2, 3}
    assert results[0].doc_id == 1


def test_hybrid_search_embeds_query_once():
    shard = build_hybrid_shard()
    model = FakeEmbeddingModel({
        "python": [1.0, 0.0],
    })

    shard.hybrid_search(
        query="python",
        embedding_model=model,
        limit=10,
    )

    assert model.calls == ["python"]


def test_hybrid_search_can_return_semantic_only_matches():
    shard = build_hybrid_shard()
    model = FakeEmbeddingModel({
        "database architecture": [0.0, 1.0],
    })

    results = shard.hybrid_search(
        query="database architecture",
        embedding_model=model,
        limit=10,
    )

    assert results
    assert results[0].doc_id == 2


def test_hybrid_search_supports_semantic_search_when_lexical_query_is_empty():
    shard = build_hybrid_shard()
    model = FakeEmbeddingModel({
        "the": [0.0, 1.0],
    })

    results = shard.hybrid_search(
        query="the",
        embedding_model=model,
        limit=10,
    )

    assert results
    assert results[0].doc_id == 2


def test_hybrid_search_requires_embedding_model():
    engine = SearchEngine(
        InvertedIndex(),
        vector_index=build_hybrid_shard().vector_index,
    )

    with pytest.raises(RuntimeError, match="embedding model"):
        engine.hybrid_search("python")


def test_hybrid_search_requires_vector_index():
    model = FakeEmbeddingModel({
        "python": [1.0, 0.0],
    })

    engine = SearchEngine(
        InvertedIndex(),
        embedding_model=model,
    )

    with pytest.raises(RuntimeError, match="vector index"):
        engine.hybrid_search("python")


def test_hybrid_search_respects_limit():
    shard = build_hybrid_shard()
    model = FakeEmbeddingModel({
        "python": [1.0, 0.0],
    })

    results = shard.hybrid_search(
        query="python",
        embedding_model=model,
        limit=2,
    )

    assert len(results) == 2


def test_hybrid_search_empty_query_returns_empty_without_embedding():
    shard = build_hybrid_shard()
    model = FakeEmbeddingModel({})

    results = shard.hybrid_search(
        query="",
        embedding_model=model,
    )

    assert results == []
    assert model.calls == []