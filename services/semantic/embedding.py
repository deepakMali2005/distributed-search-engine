from __future__ import annotations

from typing import Any, Protocol

from .models import Embedding


class EmbeddingModel(Protocol):
    """
    Interface implemented by document/query embedding models.

    Both document text and search queries must be embedded using
    the same model so that their vectors exist in the same vector
    space.
    """

    @property
    def dimension(self) -> int:
        """Return the fixed vector dimension produced by the model."""
        ...

    def embed(self, text: str) -> Embedding:
        """Convert text into an embedding in the model's vector space."""
        ...


class SentenceTransformerEmbeddingModel:
    """
    EmbeddingModel implementation backed by Sentence Transformers.

    The underlying model is loaded once when this class is created.
    Both document and query text should use the same instance/model
    configuration.
    """

    DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError(
                "model_name must not be empty."
            )

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required to use "
                "SentenceTransformerEmbeddingModel. "
                "Install project dependencies first."
            ) from exc

        model_kwargs: dict[str, Any] = {
            "trust_remote_code": False,
        }

        if device is not None:
            model_kwargs["device"] = device

        self._model = SentenceTransformer(
            model_name,
            **model_kwargs,
        )

        dimension = self._model.get_sentence_embedding_dimension()

        if dimension is None or dimension <= 0:
            raise ValueError(
                "Embedding model must expose a positive embedding dimension."
            )

        self._dimension = int(dimension)

    @property
    def dimension(self) -> int:
        """Return the embedding dimension produced by the model."""
        return self._dimension

    def embed(self, text: str) -> Embedding:
        """
        Convert text into a normalized embedding.

        Normalization makes the generated vectors unit length,
        while cosine_similarity remains the canonical similarity
        operation used by the search engine.
        """

        if not isinstance(text, str):
            raise TypeError(
                "text must be a string."
            )

        if not text.strip():
            raise ValueError(
                "text must not be empty."
            )

        vector = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        embedding = Embedding(vector.tolist())

        if embedding.dimension != self._dimension:
            raise ValueError(
                "Embedding model returned an unexpected dimension: "
                f"{embedding.dimension} != {self._dimension}."
            )

        return embedding