from services.search_api.database import SessionLocal
from services.storage.storage import save_document
from services.indexer.indexer import Indexer


def test_index_single_document():
    db = SessionLocal()

    url = "https://example.com/indexer-test"
    document = None

    try:
        document, change_type = save_document(
            db=db,
            url=url,
            title="Indexer Test",
            content="Python is a powerful programming language.",
            content_type="text/html",
        )

        indexer = Indexer()

        indexer.index_all_documents(db)

        index = indexer.get_index()

        postings = index.get_postings("python")

        document_posting = next(
            posting
            for posting in postings
            if posting.doc_id == document.id
        )

        assert document_posting.doc_id == document.id
        assert document_posting.term_frequency == 1

    finally:
        if document is not None:
            db.delete(document)
            db.commit()

        db.close()


def test_index_multiple_documents():
    db = SessionLocal()

    urls = [
        "https://example.com/indexer-test-1",
        "https://example.com/indexer-test-2",
    ]

    try:
        document1, change_type1 = save_document(
            db=db,
            url=urls[0],
            title="Python",
            content="Python is a programming language.",
            content_type="text/html",
        )

        document2, change_type2 = save_document(
            db=db,
            url=urls[1],
            title="Search",
            content="Python search engines use indexes.",
            content_type="text/html",
        )

        indexer = Indexer()

        indexer.index_all_documents(db)

        index = indexer.get_index()

        postings = index.get_postings("python")

        document_ids = [posting.doc_id for posting in postings]

        assert document1.id in document_ids
        assert document2.id in document_ids

    finally:
        for url in urls:
            from services.storage.storage import get_document_by_url

            document = get_document_by_url(db, url)

            if document is not None:
                db.delete(document)

        db.commit()
        db.close()


def test_indexer_uses_analyzer():
    indexer = Indexer()

    indexer.index_document(
        document_id=100,
        content="The Python programming language",
    )

    index = indexer.get_index()

    assert index.contains("python")
    assert index.contains("program")
    assert index.contains("languag")

    assert not index.contains("the")


def test_index_document_directly():
    indexer = Indexer()

    indexer.index_document(
        document_id=42,
        content="Python Python search engine",
    )

    index = indexer.get_index()

    postings = index.get_postings("python")

    assert len(postings) == 1
    assert postings[0].doc_id == 42
    assert postings[0].term_frequency == 2
    assert postings[0].positions == [0, 1]


def test_reindex_document():
    indexer = Indexer()

    indexer.index_document(
        document_id=1,
        content="Python Python search",
    )

    indexer.index_document(
        document_id=1,
        content="Database engine",
    )

    index = indexer.get_index()

    assert index.get_postings("python") == []

    postings = index.get_postings("databas")

    assert len(postings) == 1
    assert postings[0].doc_id == 1

    assert index.document_length(1) == 2


def test_remove_document():
    indexer = Indexer()

    indexer.index_document(
        document_id=1,
        content="Python search engine",
    )

    indexer.remove_document(1)

    index = indexer.get_index()

    assert index.document_count == 0
    assert index.get_postings("python") == []
    assert index.get_postings("search") == []
    assert index.get_postings("engin") == []