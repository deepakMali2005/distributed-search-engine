from pydantic import BaseModel, Field


class IndexDocumentRequest(BaseModel):
    document_id: int = Field(gt=0)
    tokens: list[str]
    embedding: list[float] | None = None


class IndexDocumentBatchItem(BaseModel):
    document_id: int = Field(gt=0)
    tokens: list[str]
    embedding: list[float] | None = None


class IndexDocumentBatchRequest(BaseModel):
    documents: list[IndexDocumentBatchItem] = Field(
        min_length=1,
        max_length=500,
    )


class IndexDocumentResponse(BaseModel):
    shard_id: str
    document_id: int


class IndexDocumentBatchResponse(BaseModel):
    shard_id: str
    document_count: int


class DeleteDocumentResponse(BaseModel):
    shard_id: str
    document_id: int


class SemanticSearchRequest(BaseModel):
    embedding: list[float]


class SearchResultResponse(BaseModel):
    doc_id: int
    score: float


class SemanticSearchResponse(BaseModel):
    shard_id: str
    results: list[SearchResultResponse]


class SearchResponse(BaseModel):
    shard_id: str
    results: list[SearchResultResponse]


class HealthResponse(BaseModel):
    status: str
    shard_id: str


class DocumentPresenceResponse(BaseModel):
    document_id: int
    shard_id: str