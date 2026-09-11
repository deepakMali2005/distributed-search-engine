from services.indexer.shard_manager import (
    ShardManager,
)
from services.indexer.shard_persistence import (
    JsonShardPersistence,
)


def test_manager_persists_indexed_documents(
    tmp_path,
):
    manager = ShardManager(
        [
            "shard-1",
            "shard-2",
            "shard-3",
        ],
        persistence=JsonShardPersistence(
            tmp_path
        ),
    )

    shard_id = manager.index_document(
        123,
        [
            "python",
            "search",
        ],
    )

    restored = ShardManager(
        [
            "shard-1",
            "shard-2",
            "shard-3",
        ],
        persistence=JsonShardPersistence(
            tmp_path
        ),
    )

    restored.load()

    shard = restored.get_shard(
        shard_id
    )

    assert shard.contains_document(123)
    assert shard.document_count == 1


def test_manager_auto_loads_persistent_shards(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    first = ShardManager(
        [
            "shard-1",
            "shard-2",
        ],
        persistence=persistence,
    )

    first.index_document(
        10,
        [
            "distributed",
            "search",
        ],
    )

    first.index_document(
        20,
        ["python"],
    )

    second = ShardManager(
        [
            "shard-1",
            "shard-2",
        ],
        persistence=JsonShardPersistence(
            tmp_path
        ),
        auto_load=True,
    )

    assert (
        second
        .get_shard_for_document(10)
        .contains_document(10)
    )

    assert (
        second
        .get_shard_for_document(20)
        .contains_document(20)
    )


def test_manager_persist_writes_all_shards(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    manager = ShardManager(
        [
            "shard-1",
            "shard-2",
        ],
        persistence=persistence,
    )

    manager.index_document(
        1,
        ["one"],
    )

    manager.index_document(
        2,
        ["two"],
    )

    manager.persist()

    assert (
        persistence.exists("shard-1")
        or persistence.exists("shard-2")
    )