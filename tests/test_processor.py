"""
Tests for the document processor.
"""

from services.processor.processor import clean_text


def test_clean_text_removes_extra_whitespace():
    """
    The processor should convert repeated whitespace
    into a single space.
    """

    raw_text = """
        Search engine


        is a software system
        designed to search information.
    """

    cleaned_text = clean_text(raw_text)

    assert cleaned_text == (
        "Search engine is a software system "
        "designed to search information."
    )


def test_clean_text_removes_leading_and_trailing_whitespace():
    """
    The processor should remove whitespace surrounding
    the actual document content.
    """

    raw_text = "   Hello search engine   "

    cleaned_text = clean_text(raw_text)

    assert cleaned_text == "Hello search engine"