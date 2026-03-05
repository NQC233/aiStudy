from typing import Any

from pydantic import BaseModel, Field


class AssetPdfDescriptor(BaseModel):
    asset_id: str
    file_id: str
    file_type: str
    mime_type: str
    size: int
    url: str


class ParsedDocumentPage(BaseModel):
    page_id: str
    page_no: int
    source_page_idx: int
    width: float | None = None
    height: float | None = None
    blocks: list[str] = Field(default_factory=list)


class ParsedDocumentSection(BaseModel):
    section_id: str
    title: str
    level: int
    parent_id: str | None = None
    page_start: int
    page_end: int
    block_ids: list[str] = Field(default_factory=list)


class ParsedDocumentBlock(BaseModel):
    block_id: str
    type: str
    page_no: int
    source_page_idx: int
    order: int
    section_id: str
    bbox: list[float] | None = None
    text: str | None = None
    text_level: int | None = None
    paragraph_no: int | None = None
    anchor: dict[str, Any] = Field(default_factory=dict)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    resource_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocumentTocItem(BaseModel):
    section_id: str
    title: str
    level: int
    page_start: int


class ParsedDocumentResourceCollection(BaseModel):
    images: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)


class ParsedDocumentPayload(BaseModel):
    schema_version: str
    asset_id: str
    parse_id: str
    provider: dict[str, Any] = Field(default_factory=dict)
    document: dict[str, Any] = Field(default_factory=dict)
    pages: list[ParsedDocumentPage] = Field(default_factory=list)
    sections: list[ParsedDocumentSection] = Field(default_factory=list)
    blocks: list[ParsedDocumentBlock] = Field(default_factory=list)
    assets: ParsedDocumentResourceCollection = Field(default_factory=ParsedDocumentResourceCollection)
    reading_order: list[str] = Field(default_factory=list)
    toc: list[ParsedDocumentTocItem] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class AssetParsedDocumentResponse(BaseModel):
    asset_id: str
    parse_status: str
    parse_id: str | None = None
    parsed_json: ParsedDocumentPayload | None = None
