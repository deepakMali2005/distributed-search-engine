from unittest.mock import Mock

from services.indexer.worker_service import (
    IndexerWorkerService,
)


def test_shutdown_request_sets_shutdown_flag():
    worker = Mock()
    consumer = Mock()
    db = Mock()

    service = IndexerWorkerService(
        worker=worker,
        consumer=consumer,
        db=db,
    )

    assert service._shutdown_requested is False

    service.request_shutdown()

    assert service._shutdown_requested is True


def test_run_subscribes_and_processes_until_shutdown():
    worker = Mock()
    consumer = Mock()
    db = Mock()

    service = IndexerWorkerService(
        worker=worker,
        consumer=consumer,
        db=db,
    )

    def run_once():
        service.request_shutdown()

    worker.run_once.side_effect = run_once

    service.run()

    consumer.subscribe.assert_called_once()
    worker.run_once.assert_called_once()
    consumer.close.assert_called_once()
    db.close.assert_called_once()


def test_close_releases_consumer_and_database():
    worker = Mock()
    consumer = Mock()
    db = Mock()

    service = IndexerWorkerService(
        worker=worker,
        consumer=consumer,
        db=db,
    )

    service.close()

    consumer.close.assert_called_once()
    db.close.assert_called_once()


def test_run_closes_resources_when_worker_fails():
    worker = Mock()
    consumer = Mock()
    db = Mock()

    service = IndexerWorkerService(
        worker=worker,
        consumer=consumer,
        db=db,
    )

    worker.run_once.side_effect = RuntimeError(
        "processing failure"
    )

    try:
        service.run()
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Expected worker failure to propagate"
        )

    consumer.close.assert_called_once()
    db.close.assert_called_once()