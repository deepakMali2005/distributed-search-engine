import hashlib
from urllib.parse import urldefrag

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from libs.models import CrawlFrontier, CrawlSession


class CrawlStorage:
    """Persistence operations for resumable crawl sessions."""

    SESSION_RUNNING = "running"
    SESSION_COMPLETED = "completed"

    FRONTIER_PENDING = "pending"
    FRONTIER_PROCESSING = "processing"
    FRONTIER_COMPLETED = "completed"
    FRONTIER_FAILED = "failed"

    def normalize_url(self, url: str) -> str:
        normalized, _ = urldefrag(url.strip())
        return normalized

    def session_key(
        self,
        seed_url: str,
        max_depth: int | None,
    ) -> str:
        normalized_seed = self.normalize_url(seed_url)

        depth = (
            "unlimited"
            if max_depth is None
            else str(max_depth)
        )

        value = f"{normalized_seed}|depth={depth}"

        return hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()

    def get_or_create_session(
        self,
        db: Session,
        seed_url: str,
        allowed_domain: str,
        max_depth: int | None,
    ) -> CrawlSession:
        normalized_seed = self.normalize_url(seed_url)

        key = self.session_key(
            normalized_seed,
            max_depth,
        )

        session = (
            db.query(CrawlSession)
            .filter(
                CrawlSession.session_key == key
            )
            .first()
        )

        if session is not None:
            session.status = self.SESSION_RUNNING

            db.commit()
            db.refresh(session)

            return session

        statement = (
            insert(CrawlSession)
            .values(
                session_key=key,
                seed_url=normalized_seed,
                allowed_domain=allowed_domain,
                max_depth=max_depth,
                status=self.SESSION_RUNNING,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    CrawlSession.session_key
                ]
            )
        )

        db.execute(statement)
        db.commit()

        session = (
            db.query(CrawlSession)
            .filter(
                CrawlSession.session_key == key
            )
            .one()
        )

        return session

    def enqueue_url(
        self,
        db: Session,
        crawl_session_id: int,
        url: str,
        depth: int,
    ) -> bool:
        normalized_url = self.normalize_url(url)

        statement = (
            insert(CrawlFrontier)
            .values(
                crawl_session_id=crawl_session_id,
                url=normalized_url,
                depth=depth,
                status=self.FRONTIER_PENDING,
                attempts=0,
            )
            .on_conflict_do_nothing(
                constraint="uq_crawl_frontier_session_url"
            )
            .returning(CrawlFrontier.id)
        )

        frontier_id = db.execute(
            statement
        ).scalar_one_or_none()

        db.commit()

        return frontier_id is not None

    def recover_processing(
        self,
        db: Session,
        crawl_session_id: int,
    ) -> int:
        """Return interrupted processing items to pending."""

        count = (
            db.query(CrawlFrontier)
            .filter(
                CrawlFrontier.crawl_session_id
                == crawl_session_id,
                CrawlFrontier.status
                == self.FRONTIER_PROCESSING,
            )
            .update(
                {
                    CrawlFrontier.status:
                        self.FRONTIER_PENDING,
                },
                synchronize_session=False,
            )
        )

        db.commit()

        return count

    def retry_failed(
        self,
        db: Session,
        crawl_session_id: int,
        max_attempts: int = 3,
    ) -> int:
        """Retry failed URLs that still have retry capacity."""

        count = (
            db.query(CrawlFrontier)
            .filter(
                CrawlFrontier.crawl_session_id
                == crawl_session_id,
                CrawlFrontier.status
                == self.FRONTIER_FAILED,
                CrawlFrontier.attempts < max_attempts,
            )
            .update(
                {
                    CrawlFrontier.status:
                        self.FRONTIER_PENDING,
                },
                synchronize_session=False,
            )
        )

        db.commit()

        return count

    def claim_next(
        self,
        db: Session,
        crawl_session_id: int,
    ) -> CrawlFrontier | None:
        """Claim the oldest pending URL."""

        frontier = (
            db.query(CrawlFrontier)
            .filter(
                CrawlFrontier.crawl_session_id
                == crawl_session_id,
                CrawlFrontier.status
                == self.FRONTIER_PENDING,
            )
            .order_by(
                CrawlFrontier.id.asc()
            )
            .with_for_update(
                skip_locked=True
            )
            .first()
        )

        if frontier is None:
            return None

        frontier.status = (
            self.FRONTIER_PROCESSING
        )

        frontier.attempts += 1

        db.commit()
        db.refresh(frontier)

        return frontier

    def mark_completed(
        self,
        db: Session,
        frontier_id: int,
    ) -> None:
        frontier = db.get(
            CrawlFrontier,
            frontier_id,
        )

        if frontier is None:
            return

        frontier.status = (
            self.FRONTIER_COMPLETED
        )

        frontier.last_error = None

        db.commit()

    def mark_failed(
        self,
        db: Session,
        frontier_id: int,
        error: str,
    ) -> None:
        frontier = db.get(
            CrawlFrontier,
            frontier_id,
        )

        if frontier is None:
            return

        frontier.status = (
            self.FRONTIER_FAILED
        )

        frontier.last_error = error[:2000]

        db.commit()

    def pending_count(
        self,
        db: Session,
        crawl_session_id: int,
    ) -> int:
        return int(
            db.query(
                func.count(
                    CrawlFrontier.id
                )
            )
            .filter(
                CrawlFrontier.crawl_session_id
                == crawl_session_id,
                CrawlFrontier.status.in_(
                    [
                        self.FRONTIER_PENDING,
                        self.FRONTIER_PROCESSING,
                    ]
                ),
            )
            .scalar()
            or 0
        )

    def completed_count(
        self,
        db: Session,
        crawl_session_id: int,
    ) -> int:
        return int(
            db.query(
                func.count(
                    CrawlFrontier.id
                )
            )
            .filter(
                CrawlFrontier.crawl_session_id
                == crawl_session_id,
                CrawlFrontier.status
                == self.FRONTIER_COMPLETED,
            )
            .scalar()
            or 0
        )

    def failed_count(
        self,
        db: Session,
        crawl_session_id: int,
    ) -> int:
        return int(
            db.query(
                func.count(
                    CrawlFrontier.id
                )
            )
            .filter(
                CrawlFrontier.crawl_session_id
                == crawl_session_id,
                CrawlFrontier.status
                == self.FRONTIER_FAILED,
            )
            .scalar()
            or 0
        )

    def get_session(
        self,
        db: Session,
        seed_url: str,
        max_depth: int | None,
    ) -> CrawlSession | None:
        key = self.session_key(
            seed_url=seed_url,
            max_depth=max_depth,
        )

        return (
            db.query(CrawlSession)
            .filter(
                CrawlSession.session_key == key
            )
            .first()
        )

    def delete_session(
        self,
        db: Session,
        seed_url: str,
        max_depth: int | None,
    ) -> bool:
        session = self.get_session(
            db=db,
            seed_url=seed_url,
            max_depth=max_depth,
        )

        if session is None:
            return False

        db.delete(session)
        db.commit()

        return True

    def mark_session_completed(
        self,
        db: Session,
        crawl_session_id: int,
    ) -> None:
        session = db.get(
            CrawlSession,
            crawl_session_id,
        )

        if session is None:
            return

        session.status = (
            self.SESSION_COMPLETED
        )

        db.commit()