from dataclasses import dataclass, field


@dataclass
class Posting:
    """
    Represents all occurrences of a term within a single document.
    """

    doc_id: int
    term_frequency: int = 0
    positions: list[int] = field(default_factory=list)

    def add_occurrence(self, position: int) -> None:
        """Record one occurrence of the term."""
        self.term_frequency += 1
        self.positions.append(position)


class InvertedIndex:
    """
    In-memory inverted index.

    Structure:

        term -> document_id -> Posting

    Example:

        {
            "python": {
                1: Posting(
                    doc_id=1,
                    term_frequency=2,
                    positions=[0, 4],
                )
            }
        }
    """

    def __init__(self) -> None:
        self._postings: dict[str, dict[int, Posting]] = {}
        self._document_lengths: dict[int, int] = {}

    def add_document(
        self,
        doc_id: int,
        tokens: list[str],
    ) -> None:
        """
        Add a document to the index.

        If the document already exists, its previous
        index data is removed before adding the new version.
        """

        self.remove_document(doc_id)

        self._document_lengths[doc_id] = len(tokens)

        for position, token in enumerate(tokens):
            if not token:
                continue

            term_postings = self._postings.setdefault(
                token,
                {},
            )

            posting = term_postings.get(doc_id)

            if posting is None:
                posting = Posting(doc_id=doc_id)
                term_postings[doc_id] = posting

            posting.add_occurrence(position)

    def remove_document(
        self,
        doc_id: int,
    ) -> None:
        """
        Remove a document and all of its postings.
        """

        self._document_lengths.pop(doc_id, None)

        empty_terms: list[str] = []

        for term, term_postings in self._postings.items():
            term_postings.pop(doc_id, None)

            if not term_postings:
                empty_terms.append(term)

        for term in empty_terms:
            del self._postings[term]

    def get_postings(
        self,
        term: str,
    ) -> list[Posting]:
        """
        Return all postings for a term.

        Postings are returned in ascending document ID order.
        """

        term_postings = self._postings.get(term, {})

        return [
            term_postings[doc_id]
            for doc_id in sorted(term_postings)
        ]

    def document_length(
        self,
        doc_id: int,
    ) -> int:
        """
        Return the number of tokens indexed for a document.
        """

        return self._document_lengths.get(doc_id, 0)

    def document_frequency(
        self,
        term: str,
    ) -> int:
        """
        Return the number of documents containing the term.
        """

        return len(
            self._postings.get(term, {})
        )

    def contains(
        self,
        term: str,
    ) -> bool:
        """
        Return True if the term exists in the vocabulary.
        """

        return term in self._postings

    def clear(self) -> None:
        """
        Remove all index data.
        """

        self._postings.clear()
        self._document_lengths.clear()

    # ---------------------------------------------------------
    # Persistence helpers
    # ---------------------------------------------------------

    def set_document_length(
        self,
        doc_id: int,
        length: int,
    ) -> None:
        """
        Restore a document length from persistent storage.
        """

        self._document_lengths[doc_id] = length

    def set_posting(
        self,
        term: str,
        posting: Posting,
    ) -> None:
        """
        Restore a posting from persistent storage.
        """

        self._postings.setdefault(
            term,
            {},
        )[posting.doc_id] = posting

    # ---------------------------------------------------------
    # Index statistics
    # ---------------------------------------------------------

    @property
    def document_count(self) -> int:
        """
        Return the number of indexed documents.
        """

        return len(self._document_lengths)

    @property
    def vocabulary_size(self) -> int:
        """
        Return the number of unique terms.
        """

        return len(self._postings)

    @property
    def document_ids(self) -> set[int]:
        """
        Return all document IDs currently stored in the index.
        """

        return set(self._document_lengths)

    @property
    def terms(self) -> set[str]:
        """
        Return all terms currently in the vocabulary.
        """

        return set(self._postings)

    @property
    def document_lengths(self) -> dict[int, int]:
        """
        Return document lengths.

        A copy is returned so callers cannot accidentally
        modify the internal state.
        """

        return dict(self._document_lengths)