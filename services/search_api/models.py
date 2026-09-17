from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    """
    Retrieval mode exposed by the Search API.
    """

    lexical = "lexical"
    semantic = "semantic"
    hybrid = "hybrid"


class SearchResultResponse(BaseModel):
    """
    A single search result returned by the API.
    """

    doc_id: int
    score: float
    title: str | None = None
    url: str | None = None
    snippet: str | None = None


class SearchResponse(BaseModel):
    """
    Public response contract for distributed search.
    """

    query: str
    mode: SearchMode
    results: list[SearchResultResponse]

    total_shards: int = Field(ge=0)
    successful_shards: int = Field(ge=0)
    failed_shards: int = Field(ge=0)
    timed_out_shards: int = Field(ge=0)

    partial: bool