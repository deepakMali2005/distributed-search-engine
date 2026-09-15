import pytest

from services.semantic.models import Embedding
from services.semantic.similarity import cosine_similarity


def test_identical_vectors_have_similarity_one() -> None:
    embedding = Embedding([1.0, 2.0, 3.0])

    assert cosine_similarity(embedding, embedding) == pytest.approx(1.0)


def test_orthogonal_vectors_have_similarity_zero() -> None:
    left = Embedding([1.0, 0.0])
    right = Embedding([0.0, 1.0])

    assert cosine_similarity(left, right) == pytest.approx(0.0)


def test_opposite_vectors_have_similarity_negative_one() -> None:
    left = Embedding([1.0, 0.0])
    right = Embedding([-1.0, 0.0])

    assert cosine_similarity(left, right) == pytest.approx(-1.0)


def test_similarity_is_symmetric() -> None:
    left = Embedding([1.0, 2.0, 3.0])
    right = Embedding([4.0, 5.0, 6.0])

    assert cosine_similarity(left, right) == pytest.approx(
        cosine_similarity(right, left)
    )


def test_similarity_rejects_different_dimensions() -> None:
    left = Embedding([1.0, 2.0])
    right = Embedding([1.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="same dimension"):
        cosine_similarity(left, right)


def test_similarity_rejects_zero_vector() -> None:
    zero = Embedding([0.0, 0.0])
    non_zero = Embedding([1.0, 2.0])

    with pytest.raises(ValueError, match="zero-vector"):
        cosine_similarity(zero, non_zero)


def test_similarity_rejects_zero_vector_on_right_side() -> None:
    non_zero = Embedding([1.0, 2.0])
    zero = Embedding([0.0, 0.0])

    with pytest.raises(ValueError, match="zero-vector"):
        cosine_similarity(non_zero, zero)