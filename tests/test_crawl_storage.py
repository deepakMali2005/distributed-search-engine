from libs.models import Base
from services.search_api.database import SessionLocal, engine
from services.storage.crawl_storage import CrawlStorage


Base.metadata.create_all(bind=engine)


def test_crawl_storage_deduplicates_urls_and_tracks_state():
    db = SessionLocal()
    storage = CrawlStorage()

    seed_url = "https://example.com/storage-dedupe"

    try:
        session = storage.get_or_create_session(
            db=db,
            seed_url=seed_url,
            allowed_domain="example.com",
            max_depth=2,
        )

        assert storage.enqueue_url(
            db=db,
            crawl_session_id=session.id,
            url=seed_url,
            depth=0,
        ) is True

        assert storage.enqueue_url(
            db=db,
            crawl_session_id=session.id,
            url=f"{seed_url}#fragment",
            depth=0,
        ) is False

        frontier = storage.claim_next(
            db=db,
            crawl_session_id=session.id,
        )

        assert frontier is not None
        assert frontier.url == seed_url
        assert frontier.depth == 0
        assert frontier.attempts == 1
        assert frontier.status == storage.FRONTIER_PROCESSING

        storage.mark_completed(
            db=db,
            frontier_id=frontier.id,
        )

        assert storage.completed_count(
            db=db,
            crawl_session_id=session.id,
        ) == 1

        assert storage.pending_count(
            db=db,
            crawl_session_id=session.id,
        ) == 0

    finally:
        session = storage.get_session(
            db=db,
            seed_url=seed_url,
            max_depth=2,
        )

        if session is not None:
            db.delete(session)
            db.commit()

        db.close()


def test_crawl_storage_recovers_interrupted_and_failed_urls():
    db = SessionLocal()
    storage = CrawlStorage()

    seed_url = "https://example.com/storage-recovery"

    try:
        session = storage.get_or_create_session(
            db=db,
            seed_url=seed_url,
            allowed_domain="example.com",
            max_depth=2,
        )

        storage.enqueue_url(
            db=db,
            crawl_session_id=session.id,
            url=seed_url,
            depth=0,
        )

        frontier = storage.claim_next(
            db=db,
            crawl_session_id=session.id,
        )

        assert frontier is not None

        storage.recover_processing(
            db=db,
            crawl_session_id=session.id,
        )

        recovered = storage.claim_next(
            db=db,
            crawl_session_id=session.id,
        )

        assert recovered is not None
        assert recovered.id == frontier.id
        assert recovered.attempts == 2

        storage.mark_failed(
            db=db,
            frontier_id=recovered.id,
            error="temporary failure",
        )

        assert storage.failed_count(
            db=db,
            crawl_session_id=session.id,
        ) == 1

        storage.retry_failed(
            db=db,
            crawl_session_id=session.id,
            max_attempts=3,
        )

        retried = storage.claim_next(
            db=db,
            crawl_session_id=session.id,
        )

        assert retried is not None
        assert retried.id == frontier.id
        assert retried.attempts == 3

    finally:
        session = storage.get_session(
            db=db,
            seed_url=seed_url,
            max_depth=2,
        )

        if session is not None:
            db.delete(session)
            db.commit()

        db.close()