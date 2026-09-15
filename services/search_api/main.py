from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.search.coordinator import SearchCoordinator
from services.search.http_shard_client import HttpShardSearchClient
from services.search_api.database import SessionLocal
from services.search_api.models import (
    SearchMode,
    SearchResponse,
    SearchResultResponse,
)
from services.semantic.embedding import SentenceTransformerEmbeddingModel


DEFAULT_SHARD_URLS = {
    "shard-0": "http://127.0.0.1:8100",
    "shard-1": "http://127.0.0.1:8101",
    "shard-2": "http://127.0.0.1:8102",
}


def _load_shard_urls() -> dict[str, str]:
    """
    Load remote shard URLs from the environment.

    Expected format:

        INDEXER_SHARD_URLS=shard-0=http://127.0.0.1:8100,\
shard-1=http://127.0.0.1:8101,\
shard-2=http://127.0.0.1:8102
    """

    raw = os.getenv("INDEXER_SHARD_URLS")

    if not raw:
        return dict(DEFAULT_SHARD_URLS)

    shard_urls: dict[str, str] = {}

    for item in raw.split(","):
        item = item.strip()

        if not item:
            continue

        if "=" not in item:
            raise ValueError(
                "INDEXER_SHARD_URLS entries must use "
                "shard-id=url format."
            )

        shard_id, url = item.split("=", 1)

        shard_id = shard_id.strip()
        url = url.strip()

        if not shard_id:
            raise ValueError(
                "Shard ID cannot be empty."
            )

        if not url:
            raise ValueError(
                f"URL cannot be empty for {shard_id}."
            )

        shard_urls[shard_id] = url

    if not shard_urls:
        raise ValueError(
            "INDEXER_SHARD_URLS cannot be empty."
        )

    return shard_urls


def _create_shard_clients() -> list[HttpShardSearchClient]:
    """
    Create HTTP clients for all configured remote shards.
    """

    shard_urls = _load_shard_urls()

    return [
        HttpShardSearchClient(
            shard_id=shard_id,
            base_url=url,
        )
        for shard_id, url in shard_urls.items()
    ]


search_coordinator: SearchCoordinator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize distributed search dependencies once at startup.
    """

    global search_coordinator

    embedding_model = SentenceTransformerEmbeddingModel()

    search_coordinator = SearchCoordinator(
        shard_clients=_create_shard_clients(),
        embedding_model=embedding_model,
        allow_partial_results=True,
    )

    yield

    search_coordinator = None


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


def _get_search_coordinator() -> SearchCoordinator:
    if search_coordinator is None:
        raise RuntimeError(
            "Search coordinator has not been initialized."
        )

    return search_coordinator


def _to_api_response(
    *,
    query: str,
    mode: SearchMode,
    response,
) -> SearchResponse:
    """
    Convert the internal coordinator response into the
    public Search API response contract.
    """

    return SearchResponse(
        query=query,
        mode=mode,
        results=[
            SearchResultResponse(
                doc_id=result.doc_id,
                score=result.score,
            )
            for result in response.results
        ],
        total_shards=response.total_shards,
        successful_shards=response.successful_shards,
        failed_shards=response.failed_shards,
        timed_out_shards=response.timed_out_shards,
        partial=response.is_partial,
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.get("/db-test")
def database_test(
    db: Session = Depends(get_db),
):
    result = db.execute(text("SELECT 1"))

    return {
        "database": "connected",
        "result": result.scalar(),
    }


@app.get(
    "/search",
    response_model=SearchResponse,
)
def search(
    q: str = Query(..., min_length=1),
    mode: SearchMode = Query(
        SearchMode.hybrid,
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
    ),
):
    """
    Execute distributed lexical, semantic, or hybrid search.
    """

    if not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Query must not be empty.",
        )

    coordinator = _get_search_coordinator()

    try:
        if mode == SearchMode.lexical:
            response = coordinator.search(
                query=q,
                limit=limit,
            )

        elif mode == SearchMode.semantic:
            response = coordinator.semantic_search(
                query=q,
                limit=limit,
            )

        else:
            response = coordinator.hybrid_search(
                query=q,
                limit=limit,
            )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return _to_api_response(
        query=q,
        mode=mode,
        response=response,
    )


@app.get("/documents-count")
def documents_count(
    db: Session = Depends(get_db),
):
    result = db.execute(
        text("SELECT COUNT(*) FROM documents")
    )

    return {
        "documents": result.scalar()
    }


@app.get("/index-debug")
def index_debug():
    return {
        "message": (
            "Index debug is no longer exposed through the "
            "distributed search coordinator."
        )
    }


@app.get("/debug/python")
def debug_python(
    db: Session = Depends(get_db),
):
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