from services.indexer.index import InvertedIndex
from services.indexer.segment import (
    IndexSegment,
    SegmentReader,
    SegmentWriter,
)
from services.semantic.models import Embedding
from services.semantic.vector_index import VectorIndex


def test_segment_round_trip_persists_lexical_and_semantic_state(
    tmp_path,
):
    index = InvertedIndex()

    index.add_document(
        1,
        ["python", "search"],
    )

    vector_index = VectorIndex()

    vector_index.add_document(
        1,
        Embedding(
            [0.25, 0.75, 0.5]
        ),
    )

    segment = IndexSegment(
        segment_id="segment-000000",
        path=tmp_path / "segment-000000.json",
    )

    SegmentWriter().write(
        index=index,
        segment=segment,
        vector_index=vector_index,
    )

    snapshot = SegmentReader().read_snapshot(
        segment
    )

    assert snapshot.index.document_count == 1
    assert snapshot.index.contains("python")

    assert snapshot.vector_index.document_count == 1

    assert snapshot.vector_index.get_embedding(
        1
    ) == Embedding(
        [0.25, 0.75, 0.5]
    )


def test_segment_reader_read_preserves_legacy_lexical_api(
    tmp_path,
):
    index = InvertedIndex()

    index.add_document(
        1,
        ["python"],
    )

    segment = IndexSegment(
        segment_id="segment-000000",
        path=tmp_path / "segment-000000.json",
    )

    SegmentWriter().write(
        index=index,
        segment=segment,
    )

    loaded = SegmentReader().read(
        segment
    )

    assert loaded.document_count == 1
    assert loaded.contains("python")