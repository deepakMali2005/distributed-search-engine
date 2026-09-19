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

    with patch.object(
        crawler,
        "fetch",
        side_effect=fake_fetch,
    ):
        documents = crawler.crawl(
            "https://example.com/",
            max_pages=10,
        )

    assert len(documents) == 2

    urls = {
        document["url"]
        for document in documents
    }

    assert "https://example.com/" in urls
    assert "https://example.com/about" in urls


def test_crawler_respects_max_depth_zero():
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
                </body>
            </html>
        """,
    }

    def fake_fetch(url):
        return pages[url]

    with patch.object(
        crawler,
        "fetch",
        side_effect=fake_fetch,
    ):
        documents = crawler.crawl(
            "https://example.com/",
            max_pages=10,
            max_depth=0,
        )

    assert len(documents) == 1
    assert documents[0]["url"] == "https://example.com/"


def test_crawler_respects_max_depth_one():
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
                    <a href="/contact">Contact</a>
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
                    <a href="/team">Team</a>
                </body>
            </html>
        """,
        "https://example.com/contact": """
            <html>
                <head>
                    <title>Contact</title>
                </head>
                <body>
                    <p>Contact page</p>
                    <a href="/company">Company</a>
                </body>
            </html>
        """,
        "https://example.com/team": """
            <html>
                <head>
                    <title>Team</title>
                </head>
                <body>
                    <p>Team page</p>
                </body>
            </html>
        """,
        "https://example.com/company": """
            <html>
                <head>
                    <title>Company</title>
                </head>
                <body>
                    <p>Company page</p>
                </body>
            </html>
        """,
    }

    def fake_fetch(url):
        return pages[url]

    with patch.object(
        crawler,
        "fetch",
        side_effect=fake_fetch,
    ):
        documents = crawler.crawl(
            "https://example.com/",
            max_pages=10,
            max_depth=1,
        )

    urls = {
        document["url"]
        for document in documents
    }

    assert len(documents) == 3

    assert "https://example.com/" in urls
    assert "https://example.com/about" in urls
    assert "https://example.com/contact" in urls

    assert "https://example.com/team" not in urls
    assert "https://example.com/company" not in urls


def test_crawler_respects_max_depth_two():
    crawler = Crawler()

    pages = {
        "https://example.com/": """
            <html>
                <body>
                    <a href="/level1">Level 1</a>
                </body>
            </html>
        """,
        "https://example.com/level1": """
            <html>
                <body>
                    <a href="/level2">Level 2</a>
                </body>
            </html>
        """,
        "https://example.com/level2": """
            <html>
                <body>
                    <a href="/level3">Level 3</a>
                </body>
            </html>
        """,
        "https://example.com/level3": """
            <html>
                <body>
                    <p>Level 3</p>
                </body>
            </html>
        """,
    }

    def fake_fetch(url):
        return pages[url]

    with patch.object(
        crawler,
        "fetch",
        side_effect=fake_fetch,
    ):
        documents = crawler.crawl(
            "https://example.com/",
            max_pages=10,
            max_depth=2,
        )

    urls = {
        document["url"]
        for document in documents
    }

    assert len(documents) == 3

    assert "https://example.com/" in urls
    assert "https://example.com/level1" in urls
    assert "https://example.com/level2" in urls

    assert "https://example.com/level3" not in urls


def test_crawler_max_pages_still_limits_crawl():
    crawler = Crawler()

    pages = {
        "https://example.com/": """
            <html>
                <body>
                    <a href="/one">One</a>
                    <a href="/two">Two</a>
                    <a href="/three">Three</a>
                </body>
            </html>
        """,
        "https://example.com/one": """
            <html>
                <body>
                    <p>One</p>
                </body>
            </html>
        """,
        "https://example.com/two": """
            <html>
                <body>
                    <p>Two</p>
                </body>
            </html>
        """,
        "https://example.com/three": """
            <html>
                <body>
                    <p>Three</p>
                </body>
            </html>
        """,
    }

    def fake_fetch(url):
        return pages[url]

    with patch.object(
        crawler,
        "fetch",
        side_effect=fake_fetch,
    ):
        documents = crawler.crawl(
            "https://example.com/",
            max_pages=2,
            max_depth=10,
        )

    assert len(documents) == 2