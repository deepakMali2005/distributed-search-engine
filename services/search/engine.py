from services.indexer.index import InvertedIndex
from services.search.hybrid import HybridRanker
from services.search.models import SearchResult
from services.search.query import QueryAnalyzer
from services.search.ranking import BM25Ranker
from services.search.retrieval import CandidateRetriever
from services.semantic.embedding import EmbeddingModel
from services.semantic.vector_index import VectorIndex


class SearchEngine:
    """
    Coordinates local lexical and semantic search.

    Lexical search:
        Raw Query -> QueryAnalyzer -> CandidateRetriever -> BM25Ranker

    Hybrid search:
        Raw Query -> lexical retrieval + semantic retrieval
                  -> HybridRanker -> final SearchResult objects

    The semantic components are optional so the existing lexical-only
    SearchEngine API remains backward compatible.
    """

    def __init__(
        self,
        index: InvertedIndex,
        query_analyzer: QueryAnalyzer | None = None,
        retriever: CandidateRetriever | None = None,
        ranker: BM25Ranker | None = None,
        vector_index: VectorIndex | None = None,
        embedding_model: EmbeddingModel | None = None,
        hybrid_ranker: HybridRanker | None = None,
    ) -> None:
        self.index = index
        self.vector_index = vector_index
        self.embedding_model = embedding_model

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

        self.hybrid_ranker = (
            hybrid_ranker
            or HybridRanker()
        )

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Search the lexical index and return BM25-ranked results.
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

    def hybrid_search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Combine local BM25 and semantic retrieval into one ranking.

        The query is embedded exactly once. Semantic retrieval considers all
        vectors owned by this local index so the HybridRanker receives the
        complete local candidate set rather than an arbitrary semantic
        pre-truncation.
        """

        if not query.strip() or limit <= 0:
            return []

        if self.vector_index is None:
            raise RuntimeError(
                "A vector index is required for hybrid search."
            )

        if self.embedding_model is None:
            raise RuntimeError(
                "An embedding model is required for hybrid search."
            )

        analyzed_query = self.query_analyzer.analyze(query)

        lexical_scores: dict[int, float] = {}

        if not analyzed_query.is_empty:
            candidate_doc_ids = self.retriever.retrieve(
                analyzed_query
            )

            if candidate_doc_ids:
                lexical_scores = self.ranker.rank(
                    query=analyzed_query,
                    candidate_doc_ids=candidate_doc_ids,
                )

        query_embedding = self.embedding_model.embed(query)

        semantic_results = self.vector_index.search(
            query_embedding=query_embedding,
            top_k=self.vector_index.document_count,
        )

        semantic_scores = {
            result.doc_id: result.score
            for result in semantic_results
        }

        return self.hybrid_ranker.rank(
            lexical_scores=lexical_scores,
            semantic_scores=semantic_scores,
            limit=limit,
        )