from __future__ import annotations

from abc import ABC, abstractmethod

from services.semantic.models import Embedding


class EmbeddingModel(ABC):
    """
    Abstraction for converting text into embeddings.

    The rest of the search engine depends on this interface rather
    than on a specific machine-learning or embedding library.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of embeddings produced by the model."""
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str) -> Embedding:
        """Convert text into an embedding."""
        raise NotImplementedError