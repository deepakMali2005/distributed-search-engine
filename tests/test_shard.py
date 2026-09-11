import pytest

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard


def test_create_shard():
    index = InvertedIndex()

    shard = Shard(
        shard_id="shard-001",
        index=index,
    )

    assert shard.shard_id == "shard-001"
    assert shard.document_count == 0


def test_shard_requires_id():
    index = InvertedIndex()

    with pytest.raises(ValueError):
        Shard(
            shard_id="",
            index=index,
        )


def test_add_document_to_shard():
    shard = Shard(
        shard_id="shard-001",
        index=InvertedIndex(),
    )

    shard.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    assert shard.document_count == 1
    assert shard.contains_document(1)

    assert shard.index.contains("python")
    assert shard.index.contains("search")


def test_remove_document_from_shard():
    shard = Shard(
        shard_id="shard-001",
        index=InvertedIndex(),
    )

    shard.add_document(
        doc_id=1,
        tokens=["python"],
    )

    assert shard.contains_document(1)

    shard.remove_document(1)

    assert not shard.contains_document(1)
    assert shard.document_count == 0
    assert not shard.index.contains("python")


def test_shard_only_owns_its_documents():
    shard = Shard(
        shard_id="shard-001",
        index=InvertedIndex(),
    )

    shard.add_document(
        doc_id=10,
        tokens=["python"],
    )

    shard.add_document(
        doc_id=20,
        tokens=["distributed"],
    )

    assert shard.contains_document(10)
    assert shard.contains_document(20)

    assert shard.document_count == 2