from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query

from services.indexer.index import InvertedIndex
from services.indexer.shard import Shard
from services.semantic.models import Embedding
from services.shard.config import ShardServiceConfig
from services.shard.models import (
    DeleteDocumentResponse,
    DocumentPresenceResponse,
    HealthResponse,
    IndexDocumentBatchRequest,
    IndexDocumentBatchResponse,
    IndexDocumentRequest,
    IndexDocumentResponse,
    SearchResponse,
    SearchResultResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
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
        embedding = (
            Embedding(request.embedding)
            if request.embedding is not None
            else None
        )

        if service is not None:
            service.index_document(
                document_id=request.document_id,
                tokens=request.tokens,
                embedding=embedding,
            )
        else:
            active_shard.add_document(
                doc_id=request.document_id,
                tokens=request.tokens,
                embedding=embedding,
            )

        return IndexDocumentResponse(
            shard_id=active_shard.shard_id,
            document_id=request.document_id,
        )

    @app.post(
        "/documents/bulk",
        response_model=IndexDocumentBatchResponse,
    )
    def index_documents_bulk(
        request: IndexDocumentBatchRequest,
    ) -> IndexDocumentBatchResponse:
        """
        Bulk-index a bounded batch of already-analyzed documents.

        This endpoint exists primarily for bootstrap/reconciliation.
        One request results in one shard persistence publication.
        """

        documents = [
            (
                item.document_id,
                item.tokens,
                (
                    Embedding(item.embedding)
                    if item.embedding is not None
                    else None
                ),
            )
            for item in request.documents
        ]

        document_ids = [
            document_id
            for document_id, _, _ in documents
        ]

        if len(document_ids) != len(
            set(document_ids)
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Bulk request cannot contain "
                    "duplicate document IDs."
                ),
            )

        if service is not None:
            service.index_documents(
                documents
            )

        else:
            for (
                document_id,
                tokens,
                embedding,
            ) in documents:
                active_shard.add_document(
                    doc_id=document_id,
                    tokens=tokens,
                    embedding=embedding,
                )

        return IndexDocumentBatchResponse(
            shard_id=active_shard.shard_id,
            document_count=len(documents),
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

    @app.post(
        "/semantic-search",
        response_model=SemanticSearchResponse,
    )
    def semantic_search(
        request: SemanticSearchRequest,
        limit: int = Query(
            10,
            ge=1,
            le=100,
        ),
    ) -> SemanticSearchResponse:
        query_embedding = Embedding(
            request.embedding
        )

        if service is not None:
            results = service.semantic_search(
                query_embedding=query_embedding,
                limit=limit,
            )
        else:
            results = active_shard.semantic_search(
                query_embedding=query_embedding,
                limit=limit,
            )

        return SemanticSearchResponse(
            shard_id=active_shard.shard_id,
            results=[
                SearchResultResponse(
                    doc_id=result.doc_id,
                    score=result.score,
                )
                for result in results
            ],
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

    @app.get(
        "/documents/{document_id}",
        response_model=DocumentPresenceResponse,
    )
    def document_presence(
        document_id: int,
    ) -> DocumentPresenceResponse:
        if not active_shard.contains_document(
            document_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Document {document_id} not found"
                ),
            )

        return DocumentPresenceResponse(
            document_id=document_id,
            shard_id=active_shard.shard_id,
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