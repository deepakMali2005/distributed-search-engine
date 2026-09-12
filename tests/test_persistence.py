from services.indexer.index import InvertedIndex
from services.indexer.persistence import JsonIndexPersistence


def test_save_and_load_round_trip(tmp_path):
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=[
            "python",
            "search",
            "python",
        ],
    )

    index.add_document(
        doc_id=2,
        tokens=[
            "search",
            "engine",
        ],
    )

    persistence = JsonIndexPersistence(
        tmp_path / "index.json"
    )

    persistence.save(index)

    restored = persistence.load()

    assert restored is not None

    assert restored.document_count == 2
    assert restored.vocabulary_size == 3

    assert restored.document_length(1) == 3
    assert restored.document_length(2) == 2

    python_postings = restored.get_postings("python")

    assert len(python_postings) == 1

    assert python_postings[0].doc_id == 1
    assert python_postings[0].term_frequency == 2
    assert python_postings[0].positions == [0, 2]


def test_save_creates_persistent_file(tmp_path):
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python"],
    )

    path = tmp_path / "index.json"

    persistence = JsonIndexPersistence(path)

    persistence.save(index)

    assert path.exists()


def test_load_missing_index_returns_none(tmp_path):
    persistence = JsonIndexPersistence(
        tmp_path / "missing.json"
    )

    assert persistence.load() is None


def test_load_rejects_unsupported_format_version(tmp_path):
    path = tmp_path / "index.json"

    path.write_text(
        '{"format_version": 999}',
        encoding="utf-8",
    )

    persistence = JsonIndexPersistence(path)

    try:
        persistence.load()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Unsupported index format version."


def test_persistence_preserves_empty_documents(tmp_path):
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=[],
    )

    persistence = JsonIndexPersistence(
        tmp_path / "index.json"
    )

    persistence.save(index)

    restored = persistence.load()

    assert restored is not None

    assert restored.document_count == 1
    assert restored.document_length(1) == 0
    assert restored.vocabulary_size == 0