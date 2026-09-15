import pytest

from services.semantic.models import Embedding


def test_embedding_stores_values_as_immutable_tuple() -> None:
    embedding = Embedding([0.1, 0.2, 0.3])

    assert embedding.values == (0.1, 0.2, 0.3)
    assert embedding.dimension == 3
    assert len(embedding) == 3


def test_embedding_supports_iteration_and_indexing() -> None:
    embedding = Embedding([1, 2, 3])

    assert list(embedding) == [1.0, 2.0, 3.0]
    assert embedding[0] == 1.0
    assert embedding[2] == 3.0


def test_embedding_converts_numeric_values_to_float() -> None:
    embedding = Embedding([1, 2, 3])

    assert embedding.values == (1.0, 2.0, 3.0)


def test_embedding_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="at least one"):
        Embedding([])


def test_embedding_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        Embedding([0.1, float("nan")])

    with pytest.raises(ValueError, match="finite"):
        Embedding([0.1, float("inf")])


def test_embedding_is_immutable() -> None:
    embedding = Embedding([0.1, 0.2])

    with pytest.raises(AttributeError):
        embedding.values = (1.0, 2.0)