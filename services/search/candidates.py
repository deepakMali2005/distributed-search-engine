from __future__ import annotations


class DistributedCandidatePolicy:
    """
    Determines how many candidates each shard should return before
    global hybrid ranking.

    The requested final Top-K is intentionally expanded because a
    distributed search coordinator cannot determine the global Top-K
    correctly if every shard returns only the final K candidates.

    This policy defines an explicit approximation strategy:

        candidate_limit = max(
            final_limit * oversampling_factor,
            minimum_candidates,
        )

    The policy does not know anything about shards, retrieval methods,
    ranking, HTTP, retries, or timeouts. It only converts a final K into
    a per-shard candidate window.
    """

    def __init__(
        self,
        oversampling_factor: int = 5,
        minimum_candidates: int = 50,
        maximum_candidates: int | None = None,
    ) -> None:
        if oversampling_factor <= 0:
            raise ValueError(
                "oversampling_factor must be greater than zero."
            )

        if minimum_candidates <= 0:
            raise ValueError(
                "minimum_candidates must be greater than zero."
            )

        if maximum_candidates is not None:
            if maximum_candidates <= 0:
                raise ValueError(
                    "maximum_candidates must be greater than zero."
                )

            if maximum_candidates < minimum_candidates:
                raise ValueError(
                    "maximum_candidates cannot be smaller than "
                    "minimum_candidates."
                )

        self.oversampling_factor = oversampling_factor
        self.minimum_candidates = minimum_candidates
        self.maximum_candidates = maximum_candidates

    def candidate_limit(
        self,
        final_limit: int,
    ) -> int:
        """
        Return the number of candidates to request from each shard.

        The returned value is always at least the configured minimum
        unless an explicit maximum requires the candidate window to be
        capped.
        """

        if final_limit <= 0:
            raise ValueError(
                "final_limit must be greater than zero."
            )

        candidate_limit = max(
            final_limit * self.oversampling_factor,
            self.minimum_candidates,
        )

        if self.maximum_candidates is not None:
            candidate_limit = min(
                candidate_limit,
                self.maximum_candidates,
            )

        return candidate_limit