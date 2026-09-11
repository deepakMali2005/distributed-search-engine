import json
import os
from pathlib import Path
from typing import Any

from services.indexer.index import InvertedIndex


class IndexPersistence:
    """
    Abstract interface for persistent index storage.
    """

    def save(self, index: InvertedIndex) -> None:
        raise NotImplementedError

    def load(self) -> InvertedIndex | None:
        raise NotImplementedError


class JsonIndexPersistence(IndexPersistence):
    """
    Persist an inverted index as a JSON snapshot.

    This is intentionally behind an abstraction so that the
    persistence mechanism can later be replaced with segment files,
    shard storage, or another storage engine.
    """

    FORMAT_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, index: InvertedIndex) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self._serialize(index)

        temporary_path = self.path.with_suffix(
            self.path.suffix + ".tmp"
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

        os.replace(
            temporary_path,
            self.path,
        )

    def load(self) -> InvertedIndex | None:
        if not self.path.exists():
            return None

        with self.path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if data.get("format_version") != self.FORMAT_VERSION:
            raise ValueError(
                "Unsupported index format version."
            )

        return self._deserialize(data)

    def _serialize(
        self,
        index: InvertedIndex,
    ) -> dict[str, Any]:
        terms: dict[str, Any] = {}

        for term, postings in index._index.items():
            terms[term] = {}

            for doc_id, posting in postings.items():
                terms[term][str(doc_id)] = {
                    "term_frequency": posting.term_frequency,
                    "positions": posting.positions,
                }

        return {
            "format_version": self.FORMAT_VERSION,
            "terms": terms,
            "document_lengths": {
                str(doc_id): length
                for doc_id, length
                in index._document_lengths.items()
            },
        }

    def _deserialize(
        self,
        data: dict[str, Any],
    ) -> InvertedIndex:
        index = InvertedIndex()

        document_lengths = data.get(
            "document_lengths",
            {},
        )

        for doc_id, length in document_lengths.items():
            index.set_document_length(
                doc_id=int(doc_id),
                length=int(length),
            )

        terms = data.get(
            "terms",
            {},
        )

        for term, postings in terms.items():
            for doc_id, posting_data in postings.items():
                index.set_posting(
                    term=term,
                    doc_id=int(doc_id),
                    term_frequency=int(
                        posting_data["term_frequency"]
                    ),
                    positions=posting_data["positions"],
                )

        return index