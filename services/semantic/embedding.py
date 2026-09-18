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

    def embed(
        self,
        text: str,
    ) -> Embedding:
        """Convert a single text into an embedding."""
        ...


class SentenceTransformerEmbeddingModel:
    """
    EmbeddingModel implementation backed by Sentence Transformers.

    The underlying model is loaded once when this class is created.
    Both document and query text should use the same model/model
    configuration.
    """

    DEFAULT_MODEL_NAME = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

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
            from sentence_transformers import (
                SentenceTransformer,
            )
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

        dimension = (
            self._model
            .get_sentence_embedding_dimension()
        )

        if dimension is None or dimension <= 0:
            raise ValueError(
                "Embedding model must expose a "
                "positive embedding dimension."
            )

        self._dimension = int(
            dimension
        )

    def embed_batch(
        self,
        texts: list[str],
    ) -> list[Embedding]:
        """
        Convert multiple texts into normalized embeddings
        using one Sentence Transformer model call.
        """

        if not texts:
            return []

        for text in texts:
            if not isinstance(text, str):
                raise TypeError(
                    "texts must contain only strings."
                )

            if not text.strip():
                raise ValueError(
                    "texts must not contain empty strings."
                )

        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        embeddings = [
            Embedding(
                vector.tolist()
            )
            for vector in vectors
        ]

        if len(embeddings) != len(
            texts
        ):
            raise ValueError(
                "Embedding model returned an "
                "unexpected number of vectors."
            )

        if any(
            embedding.dimension
            != self._dimension
            for embedding in embeddings
        ):
            raise ValueError(
                "Embedding model returned an "
                "unexpected dimension."
            )

        return embeddings

    @property
    def dimension(self) -> int:
        """Return the embedding dimension produced by the model."""
        return self._dimension

    def embed(
        self,
        text: str,
    ) -> Embedding:
        """
        Convert a single text into a normalized embedding.

        Normalization makes the generated vectors unit length,
        while cosine similarity remains the canonical similarity
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

        embedding = Embedding(
            vector.tolist()
        )

        if embedding.dimension != (
            self._dimension
        ):
            raise ValueError(
                "Embedding model returned an "
                "unexpected dimension: "
                f"{embedding.dimension} != "
                f"{self._dimension}."
            )

        return embedding