from __future__ import annotations

import math

from services.semantic.models import Embedding


def cosine_similarity(
    left: Embedding,
    right: Embedding,
) -> float:
    """
    Calculate cosine similarity between two embeddings.

    Returns a value in the range [-1, 1] for valid vectors.

    Raises:
        ValueError: If the vectors have different dimensions or either
            vector has zero magnitude.
    """

    if left.dimension != right.dimension:
        raise ValueError(
            "Embeddings must have the same dimension: "
            f"{left.dimension} != {right.dimension}."
        )

    dot_product = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right)
    )

    left_magnitude = math.sqrt(
        sum(value * value for value in left)
    )

    right_magnitude = math.sqrt(
        sum(value * value for value in right)
    )

    if left_magnitude == 0.0 or right_magnitude == 0.0:
        raise ValueError(
            "Cosine similarity is undefined for a zero-vector embedding."
        )

    return dot_product / (left_magnitude * right_magnitude)