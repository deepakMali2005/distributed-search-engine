from services.search.query import QueryAnalyzer


def test_query_is_analyzed_using_same_rules_as_documents():
    analyzer = QueryAnalyzer()

    result = analyzer.analyze(
        "Python programming and distributed systems"
    )

    assert result.terms == (
        "python",
        "program",
        "distribut",
        "system",
    )


def test_empty_query_returns_no_terms():
    analyzer = QueryAnalyzer()

    result = analyzer.analyze("")

    assert result.terms == ()
    assert result.is_empty


def test_stopwords_are_removed():
    analyzer = QueryAnalyzer()

    result = analyzer.analyze(
        "the python is powerful"
    )

    assert result.terms == (
        "python",
        "power",
    )


def test_query_with_only_stopwords_is_empty():
    analyzer = QueryAnalyzer()

    result = analyzer.analyze(
        "the and or but"
    )

    assert result.is_empty
    assert result.terms == ()