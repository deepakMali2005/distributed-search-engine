import math

from services.indexer.index import InvertedIndex
from services.search.models import AnalyzedQuery


class BM25Ranker:
    """
    Ranks candidate documents using the BM25 algorithm.

    The ranker operates entirely on the local inverted index.
    This makes it suitable for both single-node and future
    shard-local search.
    """

    def __init__(
        self,
        index: InvertedIndex,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> None:
        self.index = index
        self.k1 = k1
        self.b = b

    def rank(
        self,
        query: AnalyzedQuery,
        candidate_doc_ids: set[int],
    ) -> dict[int, float]:
        """
        Calculate BM25 scores for candidate documents.

        Returns:
            Mapping of document ID to BM25 score.
        """

        if query.is_empty or not candidate_doc_ids:
            return {}

        document_count = self.index.document_count

        if document_count == 0:
            return {}

        average_document_length = self._average_document_length()

        if average_document_length == 0:
            return {}

        scores: dict[int, float] = {
            doc_id: 0.0
            for doc_id in candidate_doc_ids
        }

        for term in query.terms:
            postings = self.index.get_postings(term)

            document_frequency = self.index.document_frequency(term)

            if document_frequency == 0:
                continue

            idf = self._calculate_idf(
                document_count=document_count,
                document_frequency=document_frequency,
            )

            for posting in postings:
                if posting.doc_id not in candidate_doc_ids:
                    continue

                document_length = self.index.document_length(
                    posting.doc_id
                )

                term_frequency = posting.term_frequency

                numerator = term_frequency * (self.k1 + 1)

                denominator = (
                    term_frequency
                    + self.k1
                    * (
                        1
                        - self.b
                        + self.b
                        * (
                            document_length
                            / average_document_length
                        )
                    )
                )

                scores[posting.doc_id] += (
                    idf * numerator / denominator
                )

        return scores

    def _average_document_length(self) -> float:
        """
        Calculate the average length of all indexed documents.
        """

        if self.index.document_count == 0:
            return 0.0

        total_length = sum(
            self.index.document_length(doc_id)
            for doc_id in self.index.document_ids
        )

        return total_length / self.index.document_count

    @staticmethod
    def _calculate_idf(
        document_count: int,
        document_frequency: int,
    ) -> float:
        """
        Calculate the BM25 inverse document frequency.

        Formula:

            log(
                1 + (N - df + 0.5) / (df + 0.5)
            )
        """

        return math.log(
            1
            + (
                document_count
                - document_frequency
                + 0.5
            )
            / (
                document_frequency
                + 0.5
            )
        )