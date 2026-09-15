from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Embedding:
    """
    Immutable vector representation of text.

    An embedding is a sequence of finite numeric values produced by
    an embedding model. The dimension must remain consistent for
    vectors that will be compared with one another.
    """

    values: tuple[float, ...]

    def __init__(self, values: Iterable[Real]) -> None:
        normalized = tuple(float(value) for value in values)

        if not normalized:
            raise ValueError("Embedding must contain at least one value.")

        if not all(math.isfinite(value) for value in normalized):
            raise ValueError("Embedding values must all be finite.")

        object.__setattr__(self, "values", normalized)

    @property
    def dimension(self) -> int:
        """Return the number of dimensions in the embedding."""
        return len(self.values)

    def __len__(self) -> int:
        return self.dimension

    def __iter__(self):
        return iter(self.values)

    def __getitem__(self, index: int) -> float:
        return self.values[index]