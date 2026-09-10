from services.indexer.index import InvertedIndex
from services.search.models import AnalyzedQuery


class CandidateRetriever:
    """
    Retrieves documents that contain at least one query term.

    Responsibilities:
        - Look up query terms in the inverted index.
        - Collect matching document IDs.
        - Return unique candidate document IDs.

    Ranking is intentionally handled by BM25Ranker.
    """

    def __init__(self, index: InvertedIndex) -> None:
        self.index = index

    def retrieve(self, query: AnalyzedQuery) -> set[int]:
        """
        Return document IDs that contain at least one query term.
        """

        if query.is_empty:
            return set()

        candidates: set[int] = set()

        for term in query.terms:
            postings = self.index.get_postings(term)

            for posting in postings:
                candidates.add(posting.doc_id)

        return candidates