"""
Document Processor.

The processor sits between the Crawler and Storage layers.

Pipeline:

    Crawler
        ↓
    Raw document
        ↓
    Processor
        ↓
    Clean document
        ↓
    Storage
        ↓
    PostgreSQL


The processor is responsible for cleaning and normalizing
the content extracted by the crawler.

At this stage we intentionally keep the processor simple.
More advanced processing such as tokenization, stemming,
lemmatization, and NLP will be introduced later.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean and normalize document text.

    The function currently performs basic text normalization:

        1. Remove leading and trailing whitespace.
        2. Replace repeated whitespace with a single space.
        3. Return the cleaned text.

    Args:
        text:
            Raw text extracted from a webpage.

    Returns:
        A cleaned and normalized text string.
    """

    # Remove whitespace from the beginning and end.
    text = text.strip()

    # Replace multiple spaces, tabs, and newlines
    # with a single space.
    text = re.sub(r"\s+", " ", text)

    return text