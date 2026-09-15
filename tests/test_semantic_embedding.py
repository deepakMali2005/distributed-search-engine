from __future__ import annotations

import sys
import types

import pytest

from services.semantic.embedding import (
    SentenceTransformerEmbeddingModel,
)


class FakeSentenceTransformer:
    def __init__(
        self,
        model_name: str,
        **kwargs,
    ) -> None:
        self.model_name = model_name
        self.kwargs = kwargs

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(
        self,
        text: str,
        *,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ):
        assert convert_to_numpy is True
        assert normalize_embeddings is True
        assert text == "hello world"

        return FakeVector(
            [0.6, 0.8, 0.0]
        )


class FakeVector(list):
    def tolist(self):
        return list(self)


@pytest.fixture
def fake_sentence_transformers(
    monkeypatch,
):
    module = types.ModuleType(
        "sentence_transformers"
    )

    module.SentenceTransformer = FakeSentenceTransformer

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        module,
    )


def test_model_loads_with_default_configuration(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel()

    assert model.dimension == 3


def test_model_uses_custom_model_name(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel(
        model_name="custom-model",
    )

    assert model._model.model_name == "custom-model"


def test_model_passes_device_to_sentence_transformer(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel(
        device="cpu",
    )

    assert model._model.kwargs["device"] == "cpu"


def test_model_disables_remote_code(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel()

    assert model._model.kwargs["trust_remote_code"] is False


def test_model_embeds_text(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel()

    embedding = model.embed("hello world")

    assert embedding.values == pytest.approx(
        (0.6, 0.8, 0.0)
    )
    assert embedding.dimension == 3


def test_model_rejects_empty_model_name(
    fake_sentence_transformers,
) -> None:
    with pytest.raises(
        ValueError,
        match="model_name must not be empty",
    ):
        SentenceTransformerEmbeddingModel(
            model_name="   ",
        )


def test_model_rejects_non_string_text(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel()

    with pytest.raises(
        TypeError,
        match="text must be a string",
    ):
        model.embed(123)


def test_model_rejects_empty_text(
    fake_sentence_transformers,
) -> None:
    model = SentenceTransformerEmbeddingModel()

    with pytest.raises(
        ValueError,
        match="text must not be empty",
    ):
        model.embed("   ")


def test_model_rejects_unexpected_embedding_dimension(
    monkeypatch,
) -> None:
    class WrongDimensionModel:
        def __init__(self, model_name, **kwargs):
            pass

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(
            self,
            text,
            *,
            convert_to_numpy,
            normalize_embeddings,
        ):
            return FakeVector([1.0, 2.0])

    module = types.ModuleType(
        "sentence_transformers"
    )

    module.SentenceTransformer = WrongDimensionModel

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        module,
    )

    model = SentenceTransformerEmbeddingModel()

    with pytest.raises(
        ValueError,
        match="unexpected dimension",
    ):
        model.embed("hello world")


def test_model_raises_clear_error_when_dependency_is_missing(
    monkeypatch,
) -> None:
    real_import = __import__

    def fake_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == "sentence_transformers":
            raise ImportError("missing dependency")

        return real_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        "builtins.__import__",
        fake_import,
    )

    with pytest.raises(
        RuntimeError,
        match="sentence-transformers is required",
    ):
        SentenceTransformerEmbeddingModel()