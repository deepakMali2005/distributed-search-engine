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
from services.semantic.models import Embedding


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
        ["python", "distributed", "search"],
    )

    shard.add_document(
        2,
        ["python", "systems"],
    )

    manifest = persistence.save(
        shard
    )

    restored = make_shard()

    assert persistence.load(
        restored
    ) is True

    assert restored.document_count == 2
    assert restored.contains_document(1)
    assert restored.contains_document(2)
    assert restored.index.contains("python")

    assert (
        restored.lifecycle_state
        == ShardLifecycleState.READY
    )

    assert manifest.generation == 0


def test_save_and_load_restores_embeddings(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    first_embedding = Embedding(
        [1.0, 0.0, 0.0]
    )

    second_embedding = Embedding(
        [0.0, 1.0, 0.0]
    )

    shard.add_document(
        1,
        ["python", "search"],
        first_embedding,
    )

    shard.add_document(
        2,
        ["distributed", "systems"],
        second_embedding,
    )

    persistence.save(
        shard
    )

    restored = make_shard()

    assert persistence.load(
        restored
    ) is True

    assert (
        restored.vector_index.document_count
        == 2
    )

    assert (
        restored.vector_index.get_embedding(1)
        == first_embedding
    )

    assert (
        restored.vector_index.get_embedding(2)
        == second_embedding
    )

    results = restored.vector_index.search(
        Embedding(
            [1.0, 0.0, 0.0]
        ),
        top_k=2,
    )

    assert [
        result.doc_id
        for result in results
    ] == [1, 2]


def test_delete_persists_vector_removal(
    tmp_path,
):
    persistence = JsonShardPersistence(
        tmp_path
    )

    shard = make_shard()

    shard.add_document(
        1,
        ["python"],
        Embedding(
            [1.0, 0.0]
        ),
    )

    persistence.save(
        shard
    )

    shard.remove_document(1)

    persistence.save(
        shard
    )

    restored = make_shard()

    assert persistence.load(
        restored
    ) is True

    assert restored.document_count == 0
    assert restored.vector_index.document_count == 0

    assert not restored.vector_index.contains_document(
        1
    )


def test_save_garbage_collects_old_generations(
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

    first_path = (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000000.json"
    )

    assert first_path.is_file()

    shard.add_document(
        2,
        ["distributed"],
    )

    second = persistence.save(
        shard
    )

    second_path = (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000001.json"
    )

    assert first.generation == 0
    assert second.generation == 1

    assert second_path.is_file()

    # The first generation is no longer referenced by the
    # published manifest and should have been reclaimed.
    assert not first_path.exists()

    assert (
        second.active_segments
        == ("segment-000001",)
    )

    assert (
        persistence.read_manifest(
            "shard-001"
        )
        == second
    )


def test_cleanup_unreferenced_segments_removes_stale_files(
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

    manifest = persistence.save(
        shard
    )

    segments_dir = (
        tmp_path
        / "shard-001"
        / "segments"
    )

    stale_one = (
        segments_dir
        / "segment-999998.json"
    )

    stale_two = (
        segments_dir
        / "segment-999999.json"
    )

    stale_one.write_text(
        "{}",
        encoding="utf-8",
    )

    stale_two.write_text(
        "{}",
        encoding="utf-8",
    )

    deleted = (
        persistence.cleanup_unreferenced_segments(
            "shard-001"
        )
    )

    assert deleted == [
        "segment-999998",
        "segment-999999",
    ]

    assert not stale_one.exists()
    assert not stale_two.exists()

    active_path = (
        segments_dir
        / f"{manifest.active_segments[0]}.json"
    )

    assert active_path.is_file()


def test_load_cleans_stale_generations(
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

    manifest = persistence.save(
        shard
    )

    segments_dir = (
        tmp_path
        / "shard-001"
        / "segments"
    )

    stale_path = (
        segments_dir
        / "segment-999999.json"
    )

    stale_path.write_text(
        "{}",
        encoding="utf-8",
    )

    restored = make_shard()

    assert persistence.load(
        restored
    ) is True

    assert restored.document_count == 1
    assert restored.contains_document(1)

    assert not stale_path.exists()

    active_path = (
        segments_dir
        / f"{manifest.active_segments[0]}.json"
    )

    assert active_path.is_file()


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

    persistence.save(
        shard
    )

    shard.add_document(
        2,
        ["distributed"],
    )

    persistence.save(
        shard
    )

    restored = make_shard()

    persistence.load(
        restored
    )

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

    persistence.save(
        shard
    )

    (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000000.json"
    ).unlink()

    restored = make_shard()

    try:
        persistence.load(
            restored
        )
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


def test_legacy_lexical_segment_loads_without_vectors(
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

    persistence.save(
        shard
    )

    segment_path = (
        tmp_path
        / "shard-001"
        / "segments"
        / "segment-000000.json"
    )

    payload = segment_path.read_text(
        encoding="utf-8"
    )

    assert '"vectors": {}' in payload

    import json

    data = json.loads(
        payload
    )

    data["format_version"] = 1
    data.pop(
        "vectors",
        None,
    )

    segment_path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    restored = make_shard()

    assert persistence.load(
        restored
    ) is True

    assert restored.document_count == 1

    assert (
        restored.vector_index.document_count
        == 0
    )