from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BasicResourceStatus(BaseModel):
    parse_status: str
    kb_status: str
    mindmap_status: str


class EnhancedResourceStatus(BaseModel):
    slides_status: str
    anki_status: str
    quiz_status: str


class AssetListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    source_type: str
    status: str
    created_at: datetime


class AssetDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    source_type: str
    language: str
    status: str
    parse_error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    basic_resources: BasicResourceStatus
    enhanced_resources: EnhancedResourceStatus
