from services.indexer.index import InvertedIndex, Posting
from services.indexer.segment import IndexSegment
from services.indexer.segment_manager import SegmentManager


class SegmentMerger:
    """
    Merges multiple immutable index segments into one segment.
    """

    def __init__(
        self,
        segment_manager: SegmentManager,
    ) -> None:
        self.segment_manager = segment_manager

    def merge(
        self,
        segments: list[IndexSegment],
        output_segment_id: str,
    ) -> IndexSegment:
        """
        Merge multiple segments into a single segment.

        The input segments remain untouched until the merged
        segment has been successfully written.
        """

        if not segments:
            raise ValueError(
                "At least one segment is required."
            )

        if not output_segment_id:
            raise ValueError(
                "output_segment_id cannot be empty."
            )

        merged_index = InvertedIndex()

        for segment in segments:
            index = self.segment_manager.load_segment(segment)

            self._merge_index(
                target=merged_index,
                source=index,
            )

        output_segment = (
            self.segment_manager.create_segment(
                output_segment_id
            )
        )

        self.segment_manager.write_segment(
            segment=output_segment,
            index=merged_index,
        )

        return output_segment

    def _merge_index(
        self,
        target: InvertedIndex,
        source: InvertedIndex,
    ) -> None:
        """
        Merge one index into another.
        """

        for doc_id, length in source.document_lengths.items():
            target.set_document_length(
                doc_id=doc_id,
                length=length,
            )

        for term in source.terms:
            for posting in source.get_postings(term):
                target.set_posting(
                    term=term,
                    posting=Posting(
                        doc_id=posting.doc_id,
                        term_frequency=posting.term_frequency,
                        positions=list(posting.positions),
                    ),
                )

    def merge_and_replace(
        self,
        segments: list[IndexSegment],
        output_segment_id: str,
    ) -> IndexSegment:
        """
        Merge segments into a new segment and remove the
        old segments after successful creation.
        """

        output_segment = self.merge(
            segments=segments,
            output_segment_id=output_segment_id,
        )

        # Only delete old segments after the new segment
        # has been successfully created.
        for segment in segments:
            self.segment_manager.delete_segment(segment)

        return output_segment