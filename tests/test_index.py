from services.indexer.index import InvertedIndex

def test_add_document_creates_posting():
    index = InvertedIndex()

    index.add_document(
        1,
        ["python", "is", "powerful", "python"],
    )

    postings = index.get_postings("python")

    assert len(postings) == 1

    posting = postings[0]

    assert posting.doc_id == 1
    assert posting.term_frequency == 2
    assert posting.positions == [0, 3]


def test_multiple_documents():
    index = InvertedIndex()

    index.add_document(1, ["python", "search"])
    index.add_document(2, ["python", "database"])
    index.add_document(3, ["search"])

    python_postings = index.get_postings("python")

    assert [posting.doc_id for posting in python_postings] == [1, 2]


def test_document_statistics():
    index = InvertedIndex()

    index.add_document(
        1,
        ["python", "search", "engine"],
    )

    index.add_document(
        2,
        ["database", "search"],
    )

    assert index.document_count == 2
    assert index.vocabulary_size == 4

    assert index.document_length(1) == 3
    assert index.document_length(2) == 2


def test_remove_document():
    index = InvertedIndex()

    index.add_document(1, ["python", "search"])
    index.add_document(2, ["python", "database"])

    index.remove_document(1)

    assert index.document_count == 1

    assert [p.doc_id for p in index.get_postings("python")] == [2]

    assert index.get_postings("search") == []
    assert not index.contains("search")


def test_reindexing_replaces_old_data():
    index = InvertedIndex()

    index.add_document(
        1,
        ["python", "python", "search"],
    )

    index.add_document(
        1,
        ["database", "search"],
    )

    assert index.get_postings("python") == []

    postings = index.get_postings("database")

    assert len(postings) == 1
    assert postings[0].doc_id == 1
    assert postings[0].term_frequency == 1

    assert index.document_length(1) == 2


def test_empty_document():
    index = InvertedIndex()

    index.add_document(1, [])

    assert index.document_count == 1
    assert index.document_length(1) == 0
    assert index.vocabulary_size == 0


def test_unknown_term():
    index = InvertedIndex()

    index.add_document(1, ["python"])

    assert index.get_postings("doesnotexist") == []




def test_document_frequency():
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
        tokens=["search"],
    )

    assert index.document_frequency("python") == 2
    assert index.document_frequency("search") == 2
    assert index.document_frequency("database") == 1
    assert index.document_frequency("unknown") == 0