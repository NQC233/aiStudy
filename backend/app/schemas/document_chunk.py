from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentChunkItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    parse_id: str
    chunk_index: int
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None
    block_ids: list[str] = Field(default_factory=list)
    text_content: str
    token_count: int
    embedding_status: str
    created_at: datetime


class AssetChunkListResponse(BaseModel):
    asset_id: str
    kb_status: str
    parse_id: str | None = None
    total_count: int
    chunks: list[DocumentChunkItem] = Field(default_factory=list)


class AssetChunkRebuildResponse(BaseModel):
    asset_id: str
    kb_status: str
    message: str


class AssetRetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    rewrite_query: bool = False
    strategy: str = Field(default="s0", pattern="^(s0|s1|s2|s3)$")


class RetrievalSearchHit(BaseModel):
    chunk_id: str
    score: float
    text: str
    page_start: int | None = None
    page_end: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None
    block_ids: list[str] = Field(default_factory=list)
    section_path: list[str] = Field(default_factory=list)
    quote_text: str


class AssetRetrievalSearchResponse(BaseModel):
    asset_id: str
    query: str
    top_k: int
    results: list[RetrievalSearchHit] = Field(default_factory=list)
