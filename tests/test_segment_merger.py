from services.indexer.index import InvertedIndex
from services.indexer.segment_manager import SegmentManager
from services.indexer.segment_merger import SegmentMerger


def test_merge_two_segments(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

    # Segment 1
    index1 = InvertedIndex()

    index1.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    segment1 = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment1,
        index=index1,
    )

    # Segment 2
    index2 = InvertedIndex()

    index2.add_document(
        doc_id=2,
        tokens=["distributed", "search"],
    )

    segment2 = manager.create_segment(
        "segment-000002"
    )

    manager.write_segment(
        segment=segment2,
        index=index2,
    )

    # Merge
    merged_segment = merger.merge(
        segments=[
            segment1,
            segment2,
        ],
        output_segment_id="segment-000003",
    )

    merged_index = manager.load_segment(
        merged_segment
    )

    assert merged_index.document_count == 2

    assert merged_index.contains("python")
    assert merged_index.contains("distributed")
    assert merged_index.contains("search")

    assert merged_index.document_length(1) == 2
    assert merged_index.document_length(2) == 2


def test_merge_preserves_postings(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

    index1 = InvertedIndex()

    index1.add_document(
        doc_id=1,
        tokens=[
            "python",
            "python",
            "search",
        ],
    )

    segment1 = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment1,
        index=index1,
    )

    merged_segment = merger.merge(
        segments=[segment1],
        output_segment_id="segment-000002",
    )

    merged_index = manager.load_segment(
        merged_segment
    )

    postings = merged_index.get_postings(
        "python"
    )

    assert len(postings) == 1

    posting = postings[0]

    assert posting.doc_id == 1
    assert posting.term_frequency == 2
    assert posting.positions == [0, 1]


def test_merge_does_not_modify_source_segments(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

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

    merger.merge(
        segments=[segment],
        output_segment_id="segment-000002",
    )

    original_index = manager.load_segment(
        segment
    )

    assert original_index.document_count == 1
    assert original_index.contains("python")
    assert original_index.contains("search")


def test_merge_requires_segments(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

    try:
        merger.merge(
            segments=[],
            output_segment_id="segment-000001",
        )
        assert False
    except ValueError:
        pass


def test_merge_requires_output_id(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

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

    try:
        merger.merge(
            segments=[segment],
            output_segment_id="",
        )
        assert False
    except ValueError:
        pass

def test_merge_and_replace_deletes_old_segments(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

    index1 = InvertedIndex()
    index1.add_document(
        doc_id=1,
        tokens=["python"],
    )

    segment1 = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment1,
        index=index1,
    )

    index2 = InvertedIndex()
    index2.add_document(
        doc_id=2,
        tokens=["search"],
    )

    segment2 = manager.create_segment(
        "segment-000002"
    )

    manager.write_segment(
        segment=segment2,
        index=index2,
    )

    merged_segment = merger.merge_and_replace(
        segments=[
            segment1,
            segment2,
        ],
        output_segment_id="segment-000003",
    )

    assert merged_segment.path.exists()

    assert not segment1.path.exists()
    assert not segment2.path.exists()

    segments = manager.list_segments()

    assert len(segments) == 1
    assert segments[0].segment_id == "segment-000003"


def test_merge_and_replace_preserves_data(tmp_path):
    manager = SegmentManager(tmp_path)
    merger = SegmentMerger(manager)

    index1 = InvertedIndex()

    index1.add_document(
        doc_id=1,
        tokens=["python", "python"],
    )

    segment1 = manager.create_segment(
        "segment-000001"
    )

    manager.write_segment(
        segment=segment1,
        index=index1,
    )

    index2 = InvertedIndex()

    index2.add_document(
        doc_id=2,
        tokens=["distributed", "search"],
    )

    segment2 = manager.create_segment(
        "segment-000002"
    )

    manager.write_segment(
        segment=segment2,
        index=index2,
    )

    merged_segment = merger.merge_and_replace(
        segments=[
            segment1,
            segment2,
        ],
        output_segment_id="segment-000003",
    )

    merged_index = manager.load_segment(
        merged_segment
    )

    assert merged_index.document_count == 2

    assert merged_index.contains("python")
    assert merged_index.contains("distributed")
    assert merged_index.contains("search")

    python_postings = merged_index.get_postings(
        "python"
    )

    assert python_postings[0].term_frequency == 2