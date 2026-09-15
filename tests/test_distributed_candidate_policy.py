import pytest

from services.search.candidates import (
    DistributedCandidatePolicy,
)


def test_candidate_limit_uses_minimum_candidate_window():
    policy = DistributedCandidatePolicy(
        oversampling_factor=5,
        minimum_candidates=50,
    )

    assert policy.candidate_limit(1) == 50
    assert policy.candidate_limit(5) == 50
    assert policy.candidate_limit(10) == 50


def test_candidate_limit_scales_with_final_limit():
    policy = DistributedCandidatePolicy(
        oversampling_factor=5,
        minimum_candidates=50,
    )

    assert policy.candidate_limit(20) == 100
    assert policy.candidate_limit(100) == 500


def test_candidate_limit_can_be_capped():
    policy = DistributedCandidatePolicy(
        oversampling_factor=5,
        minimum_candidates=50,
        maximum_candidates=200,
    )

    assert policy.candidate_limit(10) == 50
    assert policy.candidate_limit(20) == 100
    assert policy.candidate_limit(100) == 200


def test_invalid_oversampling_factor_is_rejected():
    with pytest.raises(ValueError):
        DistributedCandidatePolicy(
            oversampling_factor=0,
        )


def test_negative_oversampling_factor_is_rejected():
    with pytest.raises(ValueError):
        DistributedCandidatePolicy(
            oversampling_factor=-1,
        )


def test_invalid_minimum_candidates_is_rejected():
    with pytest.raises(ValueError):
        DistributedCandidatePolicy(
            minimum_candidates=0,
        )


def test_invalid_maximum_candidates_is_rejected():
    with pytest.raises(ValueError):
        DistributedCandidatePolicy(
            minimum_candidates=50,
            maximum_candidates=0,
        )


def test_maximum_candidates_cannot_be_smaller_than_minimum():
    with pytest.raises(ValueError):
        DistributedCandidatePolicy(
            minimum_candidates=100,
            maximum_candidates=50,
        )


def test_invalid_final_limit_is_rejected():
    policy = DistributedCandidatePolicy()

    with pytest.raises(ValueError):
        policy.candidate_limit(0)

    with pytest.raises(ValueError):
        policy.candidate_limit(-1)