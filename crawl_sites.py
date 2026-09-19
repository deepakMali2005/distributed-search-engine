from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

#
# When this script runs directly on the host while Docker Compose
# is running, these are the host-side ports exposed by docker-compose.
#
# Existing environment variables always take precedence.
#
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://search_user:search_password@localhost:5433/search_engine",
)

os.environ.setdefault(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

os.environ.setdefault(
    "KAFKA_DOCUMENT_EVENTS_TOPIC",
    "document-events",
)

from libs.common.kafka import KafkaConfig
from services.events.producer import DocumentEventProducer
from services.pipeline.pipeline import crawl_and_store
from services.search_api.database import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crawl one or more websites and send newly "
            "created/updated documents through the "
            "Distributed Search Engine ingestion pipeline."
        )
    )

    parser.add_argument(
        "urls",
        nargs="*",
        help=(
            "One or more starting URLs. "
            "Each URL is crawled independently."
        ),
    )

    parser.add_argument(
        "--file",
        type=Path,
        help=(
            "Optional text file containing one starting URL "
            "per line."
        ),
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help=(
            "Maximum number of pages to crawl per starting URL "
            "(default: 5)."
        ),
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help=(
            "Maximum link depth from the starting URL. "
            "0 crawls only the starting URL, 1 includes direct "
            "links, and so on. Omit for no depth restriction."
        ),
    )

    return parser.parse_args()


def load_urls(
    positional_urls: list[str],
    url_file: Path | None,
) -> list[str]:
    urls: list[str] = []

    urls.extend(
        positional_urls
    )

    if url_file is not None:
        if not url_file.exists():
            raise FileNotFoundError(
                f"URL file does not exist: {url_file}"
            )

        if not url_file.is_file():
            raise ValueError(
                f"URL path is not a file: {url_file}"
            )

        with url_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                urls.append(line)

    #
    # Remove duplicates while preserving the order supplied by
    # the user.
    #
    unique_urls: list[str] = []
    seen: set[str] = set()

    for url in urls:
        normalized = url.strip()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique_urls.append(normalized)

    return unique_urls


def validate_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            f"Unsupported URL scheme: {url}"
        )

    if not parsed.netloc:
        raise ValueError(
            f"Invalid URL: {url}"
        )


def crawl_site(
    url: str,
    max_pages: int,
    max_depth: int | None,
    event_producer: DocumentEventProducer,
) -> tuple[int, int, int]:
    """
    Crawl one starting URL.

    Returns:
        processed_count,
        created_count,
        updated_count
    """

    validate_url(
        url
    )

    print()
    print("=" * 72)
    print(
        f"CRAWLING: {url}"
    )
    print(
        f"MAX PAGES: {max_pages}"
    )
    print(
        f"MAX DEPTH: "
        f"{max_depth if max_depth is not None else 'unlimited'}"
    )
    print("=" * 72)

    db = SessionLocal()

    try:
        results = crawl_and_store(
            db=db,
            start_url=url,
            max_pages=max_pages,
            max_depth=max_depth,
            event_producer=event_producer,
        )

        created = sum(
            1
            for result in results
            if result.change_type.value == "created"
        )

        updated = sum(
            1
            for result in results
            if result.change_type.value == "updated"
        )

        unchanged = sum(
            1
            for result in results
            if result.change_type.value == "unchanged"
        )

        print()
        print(
            f"Pages processed : {len(results)}"
        )
        print(
            f"Created         : {created}"
        )
        print(
            f"Updated         : {updated}"
        )
        print(
            f"Unchanged       : {unchanged}"
        )

        for result in results:
            document = result.document

            print()
            print(
                f"[{result.change_type.value.upper()}]"
            )
            print(
                f"  ID      : {document.id}"
            )
            print(
                f"  Title   : {document.title}"
            )
            print(
                f"  URL     : {document.url}"
            )
            print(
                f"  Version : {document.version}"
            )

        return (
            len(results),
            created,
            updated,
        )

    finally:
        db.close()


def main() -> None:
    args = parse_args()

    if args.max_pages <= 0:
        raise SystemExit(
            "--max-pages must be greater than 0."
        )

    if args.max_depth is not None and args.max_depth < 0:
        raise SystemExit(
            "--max-depth must be greater than or equal to 0."
        )

    urls = load_urls(
        positional_urls=args.urls,
        url_file=args.file,
    )

    if not urls:
        raise SystemExit(
            "Provide at least one URL or use --file."
        )

    print("=" * 72)
    print("DISTRIBUTED SEARCH ENGINE - CRAWLER")
    print("=" * 72)
    print(
        f"Sites to crawl : {len(urls)}"
    )
    print(
        f"Pages per site : {args.max_pages}"
    )
    print(
        f"Max depth      : "
        f"{args.max_depth if args.max_depth is not None else 'unlimited'}"
    )
    print(
        f"Kafka          : "
        f"{os.getenv('KAFKA_BOOTSTRAP_SERVERS')}"
    )
    print()

    #
    # One producer is reused for the complete crawl run.
    #
    kafka_config = KafkaConfig.from_environment()

    event_producer = DocumentEventProducer(
        kafka_config
    )

    total_processed = 0
    total_created = 0
    total_updated = 0
    failed_sites = 0

    for url in urls:
        try:
            processed, created, updated = crawl_site(
                url=url,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
                event_producer=event_producer,
            )

            total_processed += processed
            total_created += created
            total_updated += updated

        except Exception as exc:
            failed_sites += 1

            print()
            print(
                "!" * 72
            )
            print(
                f"FAILED: {url}"
            )
            print(
                f"ERROR : {exc}"
            )
            print(
                "!" * 72
            )

    print()
    print("=" * 72)
    print("CRAWL RUN COMPLETE")
    print("=" * 72)
    print(
        f"Sites attempted : {len(urls)}"
    )
    print(
        f"Sites failed    : {failed_sites}"
    )
    print(
        f"Pages processed  : {total_processed}"
    )
    print(
        f"Documents created: {total_created}"
    )
    print(
        f"Documents updated: {total_updated}"
    )
    print("=" * 72)

    if failed_sites > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()