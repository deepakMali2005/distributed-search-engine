from services.indexer.analyzer import TextAnalyzer


def test_basic_tokenization_and_normalization():
    analyzer = TextAnalyzer()

    tokens = analyzer.analyze(
        "Python is a Powerful Programming Language."
    )

    assert tokens == [
        "python",
        "power",
        "program",
        "languag",
    ]


def test_stopwords_are_removed():
    analyzer = TextAnalyzer()

    tokens = analyzer.analyze(
        "the python is in the search engine"
    )

    assert "the" not in tokens
    assert "is" not in tokens
    assert "in" not in tokens

    assert "python" in tokens
    assert "search" in tokens
    assert "engin" in tokens


def test_repeated_terms_are_preserved():
    analyzer = TextAnalyzer()

    tokens = analyzer.analyze(
        "Python Python Python"
    )

    assert tokens == [
        "python",
        "python",
        "python",
    ]


def test_punctuation_is_removed():
    analyzer = TextAnalyzer()

    tokens = analyzer.analyze(
        "Python, search! engine? database."
    )

    assert tokens == [
        "python",
        "search",
        "engin",
        "databas",
    ]


def test_unicode_normalization():
    analyzer = TextAnalyzer()

    text = "Ｐｙｔｈｏｎ"

    tokens = analyzer.analyze(text)

    assert tokens == ["python"]


def test_empty_text():
    analyzer = TextAnalyzer()

    assert analyzer.analyze("") == []
    assert analyzer.analyze("   ") == []


def test_none_like_empty_input():
    analyzer = TextAnalyzer()

    assert analyzer.analyze("") == []