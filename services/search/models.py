from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzedQuery:
    """
    Represents a user query after text analysis.
    """

    terms: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.terms


@dataclass(frozen=True)
class SearchResult:
    """
    Represents a single search result.
    """

    doc_id: int
    score: float