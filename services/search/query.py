from services.indexer.analyzer import TextAnalyzer
from services.search.models import AnalyzedQuery


class QueryAnalyzer:
    """
    Analyzes user search queries using the same
    TextAnalyzer used during document indexing.
    """

    def __init__(
        self,
        analyzer: TextAnalyzer | None = None,
    ) -> None:
        self.analyzer = analyzer or TextAnalyzer()

    def analyze(self, query: str) -> AnalyzedQuery:
        terms = self.analyzer.analyze(query)

        return AnalyzedQuery(
            terms=tuple(terms)
        )