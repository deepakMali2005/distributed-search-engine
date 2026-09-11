from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.indexer.shard_lifecycle import (
    ShardLifecycleState,
)
from services.indexer.shard_manifest import (
    ShardManifest,
)
from services.indexer.shard_persistence import (
    JsonShardPersistence,
)


def make_shard() -> Shard:
    return Shard(
        shard_id="shard-001",
        index=InvertedIndex(),
    )


def test_save_and_load_shard(tmp_path):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    shard.add_document(
        1,
        [
            "python",
            "distributed",
            "search",
        ],
    )

    shard.add_document(
        2,
        [
            "python",
            "systems",
        ],
    )

    manifest = persistence.save(shard)

    restored = make_shard()

    assert persistence.load(
        restored
    ) is True

    assert restored.document_count == 2

    assert restored.contains_document(1)
    assert restored.contains_document(2)

    assert restored.index.contains(
        "python"
    )

    assert (
        restored.lifecycle_state
        == ShardLifecycleState.READY
    )

    assert manifest.generation == 0


def test_persistence_uses_atomic_manifest_and_immutable_generations(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    shard.add_document(
        1,
        ["python"],
    )

    first = persistence.save(
        shard
    )

    shard.add_document(
        2,
        ["distributed"],
    )

    second = persistence.save(
        shard
    )

    assert first.generation == 0
    assert second.generation == 1

    assert second.active_segments == (
        "segment-000001",
    )

    assert (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000000.json"
    ).is_file()

    assert (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000001.json"
    ).is_file()

    assert (
        persistence.read_manifest(
            "shard-001"
        )
        == second
    )


def test_load_uses_published_manifest_generation(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    shard.add_document(
        1,
        ["python"],
    )

    persistence.save(shard)

    shard.add_document(
        2,
        ["distributed"],
    )

    persistence.save(shard)

    restored = make_shard()

    persistence.load(restored)

    assert restored.document_count == 2
    assert restored.contains_document(1)
    assert restored.contains_document(2)


def test_missing_shard_is_new(tmp_path):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    assert persistence.load(
        shard
    ) is False

    assert shard.document_count == 0

    assert (
        shard.lifecycle_state
        == ShardLifecycleState.NEW
    )


def test_missing_active_segment_marks_shard_failed(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    shard.add_document(
        1,
        ["python"],
    )

    persistence.save(shard)

    (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000000.json"
    ).unlink()

    restored = make_shard()

    try:
        persistence.load(restored)

    except FileNotFoundError:
        pass

    else:
        raise AssertionError(
            "Expected missing segment failure"
        )

    assert (
        restored.lifecycle_state
        == ShardLifecycleState.FAILED
    )


def test_manifest_round_trip():
    manifest = ShardManifest(
        shard_id="shard-001",
        generation=4,
        state=ShardLifecycleState.READY,
        active_segments=(
            "segment-000004",
        ),
        document_count=10,
    )

    assert (
        ShardManifest.from_dict(
            manifest.to_dict()
        )
        == manifest
    )