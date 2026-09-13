from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.shard.config import ShardServiceConfig
from services.shard.models import (
    DeleteDocumentResponse,
    HealthResponse,
    IndexDocumentRequest,
    IndexDocumentResponse,
    SearchResponse,
    SearchResultResponse,
)
from services.shard.service import PersistentShardService


def create_shard() -> Shard:
    shard_id = os.getenv(
        "SHARD_ID",
        "shard-0",
    )

    return Shard(
        shard_id=shard_id,
        index=InvertedIndex(),
    )


def create_service(
    config: ShardServiceConfig | None = None,
) -> PersistentShardService:
    """
    Create a persistent shard service.

    When no configuration is supplied, configuration is loaded
    from environment variables. Tests can inject an explicit
    configuration.
    """

    if config is None:
        config = (
            ShardServiceConfig.from_environment()
        )

    return PersistentShardService.create(
        shard_id=config.shard_id,
        data_path=config.data_path,
    )


def create_app(
    shard: Shard | PersistentShardService | None = None,
    service: PersistentShardService | None = None,
) -> FastAPI:
    """
    Create the shard HTTP service.

    Supported forms:

        create_app(shard)

    for the original in-memory shard tests, and:

        create_app(service)

    or:

        create_app(service=service)

    for the persistent shard service.

    When no object is supplied, a persistent shard service is
    created from environment configuration.
    """

    if (
        shard is not None
        and service is not None
    ):
        raise ValueError(
            "Provide either shard or service, not both."
        )

    if isinstance(
        shard,
        PersistentShardService,
    ):
        service = shard
        active_shard = service.shard

    elif isinstance(
        shard,
        Shard,
    ):
        active_shard = shard

    elif service is not None:
        active_shard = service.shard

    else:
        service = create_service()
        active_shard = service.shard

    app = FastAPI(
        title="Distributed Search Engine Shard Service",
        version="0.1.0",
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            shard_id=active_shard.shard_id,
        )

    @app.post(
        "/documents",
        response_model=IndexDocumentResponse,
    )
    def index_document(
        request: IndexDocumentRequest,
    ) -> IndexDocumentResponse:
        if service is not None:
            service.index_document(
                document_id=request.document_id,
                tokens=request.tokens,
            )
        else:
            active_shard.add_document(
                doc_id=request.document_id,
                tokens=request.tokens,
            )

        return IndexDocumentResponse(
            shard_id=active_shard.shard_id,
            document_id=request.document_id,
        )

    @app.delete(
        "/documents/{document_id}",
        response_model=DeleteDocumentResponse,
    )
    def delete_document(
        document_id: int,
    ) -> DeleteDocumentResponse:
        if not active_shard.contains_document(
            document_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Document {document_id} not found"
                ),
            )

        if service is not None:
            service.delete_document(
                document_id
            )
        else:
            active_shard.remove_document(
                document_id
            )

        return DeleteDocumentResponse(
            shard_id=active_shard.shard_id,
            document_id=document_id,
        )

    @app.get(
        "/search",
        response_model=SearchResponse,
    )
    def search(
        q: str = Query(..., min_length=1),
        limit: int = Query(
            10,
            ge=1,
            le=100,
        ),
    ) -> SearchResponse:
        results = active_shard.search(
            query=q,
            limit=limit,
        )

        return SearchResponse(
            shard_id=active_shard.shard_id,
            results=[
                SearchResultResponse(
                    doc_id=result.doc_id,
                    score=result.score,
                )
                for result in results
            ],
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = (
        ShardServiceConfig.from_environment()
    )

    uvicorn.run(
        "services.shard.main:app",
        host=config.host,
        port=config.port,
        reload=False,
    )