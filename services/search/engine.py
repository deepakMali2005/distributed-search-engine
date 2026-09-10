from services.indexer.index import InvertedIndex
from services.search.models import SearchResult
from services.search.query import QueryAnalyzer
from services.search.ranking import BM25Ranker
from services.search.retrieval import CandidateRetriever


class SearchEngine:
    """
    Coordinates the complete search process.

    Flow:

        Raw Query
            ↓
        QueryAnalyzer
            ↓
        CandidateRetriever
            ↓
        BM25Ranker
            ↓
        SearchResult objects
    """

    def __init__(
        self,
        index: InvertedIndex,
        query_analyzer: QueryAnalyzer | None = None,
        retriever: CandidateRetriever | None = None,
        ranker: BM25Ranker | None = None,
    ) -> None:
        self.index = index

        self.query_analyzer = (
            query_analyzer
            or QueryAnalyzer()
        )

        self.retriever = (
            retriever
            or CandidateRetriever(index)
        )

        self.ranker = (
            ranker
            or BM25Ranker(index)
        )

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Search the index and return ranked results.
        """

        if not query.strip() or limit <= 0:
            return []

        analyzed_query = self.query_analyzer.analyze(query)

        if analyzed_query.is_empty:
            return []

        candidate_doc_ids = self.retriever.retrieve(
            analyzed_query
        )

        if not candidate_doc_ids:
            return []

        scores = self.ranker.rank(
            query=analyzed_query,
            candidate_doc_ids=candidate_doc_ids,
        )

        ranked_results = sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )

        return [
            SearchResult(
                doc_id=doc_id,
                score=score,
            )
            for doc_id, score in ranked_results[:limit]
        ]