from pydantic import BaseModel, Field


class IndexDocumentRequest(BaseModel):
    document_id: int = Field(gt=0)
    tokens: list[str]
    embedding: list[float] | None = None


class IndexDocumentResponse(BaseModel):
    shard_id: str
    document_id: int


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