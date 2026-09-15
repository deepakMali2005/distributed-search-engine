import math

from services.search.models import SearchResult


class HybridRanker:
    """
    Combines lexical and semantic retrieval scores into one ranking.

    Each retrieval source is normalized independently to the range [0, 1]
    before the configured weights are applied. Documents missing from one
    retrieval source receive a normalized score of 0.0 for that source.
    """

    def __init__(
        self,
        lexical_weight: float = 0.5,
        semantic_weight: float = 0.5,
    ) -> None:
        self.lexical_weight, self.semantic_weight = (
            self._normalize_weights(
                lexical_weight=lexical_weight,
                semantic_weight=semantic_weight,
            )
        )

    def rank(
        self,
        lexical_scores: dict[int, float],
        semantic_scores: dict[int, float],
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Merge lexical and semantic scores into a final ranked result list.
        """

        if limit <= 0:
            return []

        self._validate_scores(lexical_scores)
        self._validate_scores(semantic_scores)

        candidate_doc_ids = set(lexical_scores) | set(semantic_scores)

        if not candidate_doc_ids:
            return []

        normalized_lexical = self._normalize_scores(lexical_scores)
        normalized_semantic = self._normalize_scores(semantic_scores)

        hybrid_scores: dict[int, float] = {}

        for doc_id in candidate_doc_ids:
            lexical_score = normalized_lexical.get(doc_id, 0.0)
            semantic_score = normalized_semantic.get(doc_id, 0.0)

            hybrid_scores[doc_id] = (
                self.lexical_weight * lexical_score
                + self.semantic_weight * semantic_score
            )

        ranked_results = sorted(
            hybrid_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )

        return [
            SearchResult(doc_id=doc_id, score=score)
            for doc_id, score in ranked_results[:limit]
        ]

    @staticmethod
    def _normalize_scores(
        scores: dict[int, float],
    ) -> dict[int, float]:
        """
        Normalize one retrieval source using min-max normalization.

        A single retrieved document receives 1.0 because it is the only
        available candidate and therefore the strongest result for that
        retrieval source.

        When multiple documents have exactly the same score, the source has
        no ranking signal, so all normalized scores are 0.0.
        """

        if not scores:
            return {}

        minimum = min(scores.values())
        maximum = max(scores.values())

        if minimum == maximum:
            if len(scores) == 1:
                return {
                    doc_id: 1.0
                    for doc_id in scores
                }

            return {
                doc_id: 0.0
                for doc_id in scores
            }

        score_range = maximum - minimum

        return {
            doc_id: (score - minimum) / score_range
            for doc_id, score in scores.items()
        }

    @staticmethod
    def _normalize_weights(
        lexical_weight: float,
        semantic_weight: float,
    ) -> tuple[float, float]:
        """Validate and normalize the configured retrieval weights."""

        if not math.isfinite(lexical_weight):
            raise ValueError(
                "lexical_weight must be finite."
            )

        if not math.isfinite(semantic_weight):
            raise ValueError(
                "semantic_weight must be finite."
            )

        if lexical_weight < 0:
            raise ValueError(
                "lexical_weight must be non-negative."
            )

        if semantic_weight < 0:
            raise ValueError(
                "semantic_weight must be non-negative."
            )

        total_weight = lexical_weight + semantic_weight

        if total_weight <= 0:
            raise ValueError(
                "At least one ranking weight must be greater than zero."
            )

        return (
            lexical_weight / total_weight,
            semantic_weight / total_weight,
        )

    @staticmethod
    def _validate_scores(
        scores: dict[int, float],
    ) -> None:
        """Reject invalid retrieval scores before ranking."""

        for doc_id, score in scores.items():
            if not isinstance(doc_id, int):
                raise ValueError(
                    "Document IDs must be integers."
                )

            if not math.isfinite(score):
                raise ValueError(
                    "Retrieval scores must be finite."
                )