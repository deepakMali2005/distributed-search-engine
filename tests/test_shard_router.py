import pytest

from services.indexer.shard_router import ShardRouter


def test_router_requires_shards():
    with pytest.raises(ValueError):
        ShardRouter([])


def test_router_requires_positive_virtual_nodes():
    with pytest.raises(ValueError):
        ShardRouter(
            shard_ids=["shard-001"],
            virtual_nodes=0,
        )


def test_router_requires_unique_shard_ids():
    with pytest.raises(ValueError):
        ShardRouter(
            shard_ids=[
                "shard-001",
                "shard-001",
            ]
        )


def test_routes_document_to_known_shard():
    router = ShardRouter(
        shard_ids=[
            "shard-001",
            "shard-002",
            "shard-003",
        ]
    )

    shard_id = router.get_shard_id(123)

    assert shard_id in {
        "shard-001",
        "shard-002",
        "shard-003",
    }


def test_routing_is_deterministic():
    router = ShardRouter(
        shard_ids=[
            "shard-001",
            "shard-002",
            "shard-003",
        ]
    )

    first = router.get_shard_id(123)
    second = router.get_shard_id(123)

    assert first == second


def test_different_documents_can_use_multiple_shards():
    router = ShardRouter(
        shard_ids=[
            "shard-001",
            "shard-002",
            "shard-003",
        ]
    )

    assigned_shards = {
        router.get_shard_id(document_id)
        for document_id in range(1000)
    }

    assert len(assigned_shards) > 1


def test_single_shard_routes_everything_to_that_shard():
    router = ShardRouter(
        shard_ids=["shard-001"]
    )

    for document_id in range(100):
        assert (
            router.get_shard_id(document_id)
            == "shard-001"
        )


def test_virtual_nodes_create_ring():
    router = ShardRouter(
        shard_ids=[
            "shard-001",
            "shard-002",
            "shard-003",
        ],
        virtual_nodes=10,
    )

    assert len(router._ring) == 30
    assert len(router._ring_positions) == 30


def test_additional_shard_changes_some_assignments():
    router_before = ShardRouter(
        shard_ids=[
            "shard-001",
            "shard-002",
            "shard-003",
        ],
        virtual_nodes=100,
    )

    router_after = ShardRouter(
        shard_ids=[
            "shard-001",
            "shard-002",
            "shard-003",
            "shard-004",
        ],
        virtual_nodes=100,
    )

    before = {
        document_id: router_before.get_shard_id(
            document_id
        )
        for document_id in range(1000)
    }

    after = {
        document_id: router_after.get_shard_id(
            document_id
        )
        for document_id in range(1000)
    }

    moved = sum(
        before[document_id] != after[document_id]
        for document_id in before
    )

    assert moved > 0
    assert moved < 1000