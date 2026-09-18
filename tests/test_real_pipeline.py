"""
Manual real-world test for the Crawler → Storage → PostgreSQL pipeline.

Unlike the automated integration test, this script makes a real
HTTP request to Wikipedia.

Pipeline:

    Wikipedia
        ↓
    Crawler
        ↓
    Processor
        ↓
    Storage
        ↓
    PostgreSQL
        ↓
    Kafka event publication (when configured)
"""


from services.pipeline.pipeline import crawl_and_store
from services.search_api.database import SessionLocal


# Starting Wikipedia article.
START_URL = "https://en.wikipedia.org/wiki/Information_retrieval"

# Keep this small while testing the crawler.
MAX_PAGES = 5


def main():
    """Run the real Wikipedia crawling pipeline."""

    db = SessionLocal()

    try:
        print("=" * 60)
        print("REAL-WORLD CRAWLER TEST")
        print("=" * 60)

        print(f"Starting URL : {START_URL}")
        print(f"Maximum pages: {MAX_PAGES}")
        print()

        # Run the complete:
        #
        # Wikipedia → Crawler → Processor → Storage → PostgreSQL
        #
        # crawl_and_store() returns PipelineResult objects.
        results = crawl_and_store(
            db=db,
            start_url=START_URL,
            max_pages=MAX_PAGES,
        )

        print(f"Documents processed: {len(results)}")
        print()

        # Display the documents that were stored.
        for result in results:
            document = result.document

            print("-" * 60)
            print(f"Database ID : {document.id}")
            print(f"Title       : {document.title}")
            print(f"URL         : {document.url}")
            print(f"Change type : {result.change_type.value}")
            print(f"Version     : {document.version}")
            print(f"Content     : {document.content[:200]}...")

        print("-" * 60)
        print("Pipeline completed successfully!")

    finally:
        # Always close the database session.
        db.close()


if __name__ == "__main__":
    main()