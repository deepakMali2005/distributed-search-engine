from services.crawler.crawler import Crawler


def test_crawler_normalizes_relative_links():
    crawler = Crawler()

    html = """
    <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <a href="/about">About</a>
            <a href="products">Products</a>
            <a href="https://google.com">Google</a>
        </body>
    </html>
    """

    result = crawler.parse(
        html,
        "https://example.com/"
    )

    assert "https://example.com/about" in result["links"]
    assert "https://example.com/products" in result["links"]
    assert "https://google.com" in result["links"]