from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.search.service import SearchService
from services.search_api.database import SessionLocal


search_service = SearchService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize the search index when the API starts.
    """

    db = SessionLocal()

    try:
        search_service.initialize(db)
        yield
    finally:
        db.close()


app = FastAPI(
    title="Distributed Search Engine API",
    version="0.1.0",
    lifespan=lifespan,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.get("/db-test")
def database_test(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))

    return {
        "database": "connected",
        "result": result.scalar(),
    }


@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
):
    results = search_service.search(
        query=q,
        limit=limit,
    )

    return {
        "query": q,
        "results": [
            {
                "doc_id": result.doc_id,
                "score": result.score,
            }
            for result in results
        ],
    }


# Temporary endpoint
@app.get("/documents-count")
def documents_count(db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT COUNT(*) FROM documents")
    )

    return {
        "documents": result.scalar()
    }


# Temporary endpoint
@app.get("/index-debug")
def index_debug():
    index = search_service.indexer.get_index()

    return {
        "documents": index.document_count,
        "vocabulary": index.vocabulary_size,
        "python": index.contains("python"),
        "distribut": index.contains("distribut"),
        "system": index.contains("system"),
    }


# Temporary endpoint
@app.get("/debug/python")
def debug_python(db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            SELECT id, title, url
            FROM documents
            WHERE LOWER(content) LIKE '%python%'
        """)
    )

    documents = result.fetchall()

    return {
        "count": len(documents),
        "documents": [
            {
                "id": row.id,
                "title": row.title,
                "url": row.url,
            }
            for row in documents
        ],
    }