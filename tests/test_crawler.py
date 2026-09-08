from unittest.mock import patch

from services.crawler.crawler import Crawler


def test_crawler_crawls_multiple_pages():
    crawler = Crawler()

    pages = {
        "https://example.com/": """
            <html>
                <head>
                    <title>Home</title>
                </head>
                <body>
                    <p>Home page</p>
                    <a href="/about">About</a>
                </body>
            </html>
        """,
        "https://example.com/about": """
            <html>
                <head>
                    <title>About</title>
                </head>
                <body>
                    <p>About page</p>
                    <a href="/">Home</a>
                </body>
            </html>
        """,
    }

    def fake_fetch(url):
        return pages[url]

    with patch.object(crawler, "fetch", side_effect=fake_fetch):
        documents = crawler.crawl(
            "https://example.com/",
            max_pages=10,
        )

    assert len(documents) == 2

    urls = {document["url"] for document in documents}

    assert "https://example.com/" in urls
    assert "https://example.com/about" in urls