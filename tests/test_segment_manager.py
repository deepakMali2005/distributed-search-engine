from services.indexer.index import InvertedIndex
from services.indexer.segment_manager import SegmentManager


def test_create_segment(tmp_path):
    manager = SegmentManager(tmp_path)

    segment = manager.create_segment(
        "segment-000001"
    )

    assert segment.segment_id == "segment-000001"
    assert segment.path == (
        tmp_path / "segment-000001.json"
    )


def test_write_and_list_segments(tmp_path):
    manager = SegmentManager(tmp_path)

    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    segment = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment,
        index=index,
    )

    segments = manager.list_segments()

    assert len(segments) == 1
    assert segments[0].segment_id == "segment-000001"


def test_load_segment(tmp_path):
    manager = SegmentManager(tmp_path)

    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    segment = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment,
        index=index,
    )

    loaded_index = manager.load_segment(
        segment
    )

    assert loaded_index.contains("python")
    assert loaded_index.contains("search")
    assert loaded_index.document_count == 1


def test_delete_segment(tmp_path):
    manager = SegmentManager(tmp_path)

    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python"],
    )

    segment = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment,
        index=index,
    )

    assert len(manager.list_segments()) == 1

    deleted = manager.delete_segment(
        segment
    )

    assert deleted is True
    assert manager.list_segments() == []


def test_delete_missing_segment(tmp_path):
    manager = SegmentManager(tmp_path)

    segment = manager.create_segment(
        "segment-000001"
    )

    assert manager.delete_segment(
        segment
    ) is False