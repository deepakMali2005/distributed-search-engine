from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.indexer.shard_lifecycle import ShardLifecycleState
from services.indexer.shard_manifest import ShardManifest
from services.indexer.shard_persistence import JsonShardPersistence
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

    assert (
        second.active_segments
        == ("segment-000001",)
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