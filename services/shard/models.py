from pydantic import BaseModel, Field


class IndexDocumentRequest(BaseModel):
    document_id: int = Field(gt=0)
    tokens: list[str]


class IndexDocumentResponse(BaseModel):
    shard_id: str
    document_id: int


class DeleteDocumentResponse(BaseModel):
    shard_id: str
    document_id: int


class SearchResultResponse(BaseModel):
    doc_id: int
    score: float


class SearchResponse(BaseModel):
    shard_id: str
    results: list[SearchResultResponse]


class HealthResponse(BaseModel):
    status: str
    shard_id: str