from pathlib import Path

from services.indexer.segment import (
    IndexSegment,
    SegmentReader,
    SegmentWriter,
)


class SegmentManager:
    """
    Manages index segments stored on disk.

    The manager is responsible for segment lifecycle:
        - creating segment metadata
        - listing segments
        - reading segments
        - deleting segments

    Individual segments are immutable.
    """

    SEGMENT_SUFFIX = ".json"

    def __init__(
        self,
        directory: str | Path = "data/index/segments",
    ) -> None:
        self.directory = Path(directory)

        self.writer = SegmentWriter()
        self.reader = SegmentReader()

    def create_segment(
        self,
        segment_id: str,
    ) -> IndexSegment:
        """
        Create a segment reference.

        The actual segment file is not written until
        SegmentWriter.write() is called.
        """

        if not segment_id:
            raise ValueError(
                "segment_id cannot be empty."
            )

        return IndexSegment(
            segment_id=segment_id,
            path=self.directory
            / f"{segment_id}{self.SEGMENT_SUFFIX}",
        )

    def list_segments(self) -> list[IndexSegment]:
        """
        Return all segments currently stored on disk.

        Segments are returned in deterministic order.
        """

        if not self.directory.exists():
            return []

        segments = []

        for path in sorted(
            self.directory.glob(
                f"*{self.SEGMENT_SUFFIX}"
            )
        ):
            segment_id = path.stem

            segments.append(
                IndexSegment(
                    segment_id=segment_id,
                    path=path,
                )
            )

        return segments

    def write_segment(
        self,
        segment: IndexSegment,
        index,
    ) -> None:
        """
        Persist an index as a segment.
        """

        self.writer.write(
            index=index,
            segment=segment,
        )

    def load_segment(
        self,
        segment: IndexSegment,
    ):
        """
        Load a segment into an InvertedIndex.
        """

        return self.reader.read(segment)

    def delete_segment(
        self,
        segment: IndexSegment,
    ) -> bool:
        """
        Delete a segment from disk.

        Returns:
            True if the segment existed and was deleted.
            False otherwise.
        """

        if not segment.path.exists():
            return False

        segment.path.unlink()

        return True