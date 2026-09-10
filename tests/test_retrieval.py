from services.indexer.index import InvertedIndex
from services.search.models import AnalyzedQuery
from services.search.retrieval import CandidateRetriever


def test_retrieve_documents_for_single_term():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    index.add_document(
        doc_id=2,
        tokens=["database"],
    )

    retriever = CandidateRetriever(index)

    query = AnalyzedQuery(
        terms=("python",)
    )

    candidates = retriever.retrieve(query)

    assert candidates == {1}


def test_retrieve_documents_for_multiple_terms():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    index.add_document(
        doc_id=2,
        tokens=["python", "database"],
    )

    index.add_document(
        doc_id=3,
        tokens=["distributed", "system"],
    )

    retriever = CandidateRetriever(index)

    query = AnalyzedQuery(
        terms=("python", "system")
    )

    candidates = retriever.retrieve(query)

    assert candidates == {1, 2, 3}


def test_duplicate_matches_are_removed():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "python", "search"],
    )

    retriever = CandidateRetriever(index)

    query = AnalyzedQuery(
        terms=("python", "search")
    )

    candidates = retriever.retrieve(query)

    assert candidates == {1}


def test_unknown_term_returns_no_candidates():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    retriever = CandidateRetriever(index)

    query = AnalyzedQuery(
        terms=("database",)
    )

    candidates = retriever.retrieve(query)

    assert candidates == set()


def test_empty_query_returns_no_candidates():
    index = InvertedIndex()

    index.add_document(
        doc_id=1,
        tokens=["python", "search"],
    )

    retriever = CandidateRetriever(index)

    query = AnalyzedQuery(terms=())

    candidates = retriever.retrieve(query)

    assert candidates == set()