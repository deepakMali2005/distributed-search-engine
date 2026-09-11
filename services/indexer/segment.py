import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.indexer.index import InvertedIndex, Posting


@dataclass(frozen=True)
class IndexSegment:
    """
    Represents one immutable index segment.

    A segment is a self-contained snapshot of an inverted index.
    Once written, it should not be modified.
    """

    segment_id: str
    path: Path


class SegmentWriter:
    """
    Writes an InvertedIndex to an immutable segment.
    """

    FORMAT_VERSION = 1

    def write(
        self,
        index: InvertedIndex,
        segment: IndexSegment,
    ) -> None:
        """
        Write the index to disk as a segment.
        """

        segment.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self._serialize(
            index=index,
            segment_id=segment.segment_id,
        )

        temporary_path = segment.path.with_suffix(
            segment.path.suffix + ".tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        # Atomic replacement prevents a partially-written
        # segment from becoming visible.
        os.replace(
            temporary_path,
            segment.path,
        )

    def _serialize(
        self,
        index: InvertedIndex,
        segment_id: str,
    ) -> dict[str, Any]:
        """
        Convert an InvertedIndex into JSON-serializable data.
        """

        terms: dict[str, Any] = {}

        for term in index.terms:
            postings = index.get_postings(term)

            terms[term] = {}

            for posting in postings:
                terms[term][str(posting.doc_id)] = {
                    "term_frequency": posting.term_frequency,
                    "positions": posting.positions,
                }

        return {
            "format_version": self.FORMAT_VERSION,
            "segment_id": segment_id,
            "terms": terms,
            "document_lengths": {
                str(doc_id): length
                for doc_id, length
                in index.document_lengths.items()
            },
        }


class SegmentReader:
    """
    Loads an immutable index segment from disk.
    """

    FORMAT_VERSION = 1

    def read(
        self,
        segment: IndexSegment,
    ) -> InvertedIndex:
        """
        Load a segment from disk.
        """

        if not segment.path.exists():
            raise FileNotFoundError(
                f"Segment not found: {segment.path}"
            )

        with segment.path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if data.get("format_version") != self.FORMAT_VERSION:
            raise ValueError(
                "Unsupported segment format version."
            )

        return self._deserialize(data)

    def _deserialize(
        self,
        data: dict[str, Any],
    ) -> InvertedIndex:
        """
        Convert persisted segment data back into an InvertedIndex.
        """

        index = InvertedIndex()

        # Restore document lengths.
        for doc_id, length in data.get(
            "document_lengths",
            {},
        ).items():
            index.set_document_length(
                doc_id=int(doc_id),
                length=int(length),
            )

        # Restore postings.
        for term, postings in data.get(
            "terms",
            {},
        ).items():
            for doc_id, posting_data in postings.items():
                posting = Posting(
                    doc_id=int(doc_id),
                    term_frequency=int(
                        posting_data["term_frequency"]
                    ),
                    positions=[
                        int(position)
                        for position in posting_data["positions"]
                    ],
                )

                index.set_posting(
                    term=term,
                    posting=posting,
                )

        return index