from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.indexer.index import InvertedIndex, Posting
from services.semantic.models import Embedding
from services.semantic.vector_index import VectorIndex


@dataclass(frozen=True)
class IndexSegment:
    """Represents one immutable lexical + semantic index segment."""

    segment_id: str
    path: Path


@dataclass(frozen=True)
class SegmentSnapshot:
    """The complete persisted state represented by one segment."""

    index: InvertedIndex
    vector_index: VectorIndex


class SegmentWriter:
    """Writes an InvertedIndex and optional VectorIndex to one immutable segment."""

    FORMAT_VERSION = 2

    def write(
        self,
        index: InvertedIndex,
        segment: IndexSegment,
        vector_index: VectorIndex | None = None,
    ) -> None:
        """Write the complete shard snapshot to disk atomically."""
        segment.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self._serialize(
            index=index,
            segment_id=segment.segment_id,
            vector_index=vector_index,
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
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temporary_path,
            segment.path,
        )

    def _serialize(
        self,
        index: InvertedIndex,
        segment_id: str,
        vector_index: VectorIndex | None = None,
    ) -> dict[str, Any]:
        """Convert a shard snapshot into JSON-serializable data."""
        terms: dict[str, Any] = {}

        for term in index.terms:
            postings = index.get_postings(term)
            terms[term] = {}

            for posting in postings:
                terms[term][str(posting.doc_id)] = {
                    "term_frequency": posting.term_frequency,
                    "positions": posting.positions,
                }

        vectors: dict[str, Any] = {}

        if vector_index is not None:
            for doc_id in sorted(vector_index.document_ids):
                embedding = vector_index.get_embedding(doc_id)
                assert embedding is not None
                vectors[str(doc_id)] = list(embedding.values)

        return {
            "format_version": self.FORMAT_VERSION,
            "segment_id": segment_id,
            "terms": terms,
            "document_lengths": {
                str(doc_id): length
                for doc_id, length in index.document_lengths.items()
            },
            "vectors": vectors,
        }


class SegmentReader:
    """Loads immutable lexical + semantic index segments from disk."""

    LEGACY_FORMAT_VERSION = 1
    FORMAT_VERSION = 2

    def read(
        self,
        segment: IndexSegment,
    ) -> InvertedIndex:
        """
        Load only the lexical index.

        This preserves the original SegmentReader API used by the
        lexical segment manager. New shard persistence should use
        read_snapshot() so semantic vectors are restored as well.
        """
        return self.read_snapshot(segment).index

    def read_snapshot(
        self,
        segment: IndexSegment,
    ) -> SegmentSnapshot:
        """Load the complete lexical + semantic segment snapshot."""
        if not segment.path.exists():
            raise FileNotFoundError(
                f"Segment not found: {segment.path}"
            )

        with segment.path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        format_version = data.get("format_version")

        if format_version not in (
            self.LEGACY_FORMAT_VERSION,
            self.FORMAT_VERSION,
        ):
            raise ValueError(
                "Unsupported segment format version."
            )

        index = self._deserialize_index(data)
        vector_index = self._deserialize_vectors(data)

        return SegmentSnapshot(
            index=index,
            vector_index=vector_index,
        )

    def _deserialize_index(
        self,
        data: dict[str, Any],
    ) -> InvertedIndex:
        """Convert persisted lexical data back into an InvertedIndex."""
        index = InvertedIndex()

        for doc_id, length in data.get(
            "document_lengths",
            {},
        ).items():
            index.set_document_length(
                doc_id=int(doc_id),
                length=int(length),
            )

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

    def _deserialize_vectors(
        self,
        data: dict[str, Any],
    ) -> VectorIndex:
        """Restore persisted document embeddings."""
        vector_index = VectorIndex()

        for doc_id, values in data.get(
            "vectors",
            {},
        ).items():
            if not isinstance(values, list):
                raise ValueError(
                    "Invalid persisted vector data."
                )

            vector_index.add_document(
                doc_id=int(doc_id),
                embedding=Embedding(values),
            )

        return vector_index