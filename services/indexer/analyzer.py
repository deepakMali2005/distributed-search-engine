import re
import unicodedata

from nltk.stem.snowball import SnowballStemmer


class TextAnalyzer:
    """
    Converts raw document text into normalized index terms.

    The same analyzer can later be used for both:
        - document indexing
        - user query analysis
    """

    _TOKEN_PATTERN = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*", re.UNICODE)

    _STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "he",
        "her",
        "his",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "she",
        "that",
        "the",
        "their",
        "them",
        "there",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    }

    def __init__(self) -> None:
        self._stemmer = SnowballStemmer("english")

    def analyze(self, text: str) -> list[str]:
        """
        Analyze raw text and return normalized index terms.
        """

        if not text:
            return []

        normalized_text = self._normalize_unicode(text)

        raw_tokens = self._tokenize(normalized_text)

        tokens: list[str] = []

        for token in raw_tokens:
            token = token.lower()

            if token in self._STOPWORDS:
                continue

            if not self._is_valid_token(token):
                continue

            token = self._stemmer.stem(token)

            if token:
                tokens.append(token)

        return tokens

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """
        Normalize Unicode characters into a consistent representation.
        """

        return unicodedata.normalize("NFKC", text)

    def _tokenize(self, text: str) -> list[str]:
        """
        Extract word-like tokens while preserving internal
        apostrophes and hyphens.
        """

        return self._TOKEN_PATTERN.findall(text)

    @staticmethod
    def _is_valid_token(token: str) -> bool:
        """
        Reject tokens that do not contain alphabetic characters.
        """

        return any(character.isalpha() for character in token)