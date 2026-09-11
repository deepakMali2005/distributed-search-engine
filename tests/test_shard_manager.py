import pytest

from services.indexer.shard_manager import ShardManager


def test_creates_all_shards():
    manager = ShardManager(
        ["shard-1", "shard-2", "shard-3"]
    )

    assert manager.shard_count == 3


def test_get_shard():
    manager = ShardManager(
        ["shard-1", "shard-2"]
    )

    shard = manager.get_shard("shard-1")

    assert shard.shard_id == "shard-1"


def test_unknown_shard_raises():
    manager = ShardManager(
        ["shard-1"]
    )

    with pytest.raises(KeyError):
        manager.get_shard("does-not-exist")


def test_document_is_routed_to_correct_shard():
    manager = ShardManager(
        ["shard-1", "shard-2", "shard-3"]
    )

    document_id = 123

    expected_shard = manager.router.get_shard_id(
        document_id
    )

    actual_shard = manager.get_shard_for_document(
        document_id
    )

    assert actual_shard.shard_id == expected_shard


def test_index_document():
    manager = ShardManager(
        ["shard-1", "shard-2"]
    )

    document_id = 123

    shard_id = manager.index_document(
        document_id=document_id,
        tokens=["python", "distributed", "search"],
    )

    shard = manager.get_shard(shard_id)

    assert shard.contains_document(document_id)
    assert shard.document_count == 1


def test_remove_document():
    manager = ShardManager(
        ["shard-1", "shard-2"]
    )

    document_id = 123

    manager.index_document(
        document_id=document_id,
        tokens=["python", "search"],
    )

    shard_id = manager.remove_document(
        document_id
    )

    shard = manager.get_shard(shard_id)

    assert not shard.contains_document(document_id)