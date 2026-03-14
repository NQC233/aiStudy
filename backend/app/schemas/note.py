from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AnchorType = Literal["text_selection", "mindmap_node", "knowledge_point"]


class NoteAnchorPayload(BaseModel):
    anchor_type: AnchorType = "text_selection"
    page_no: int | None = Field(default=None, ge=1)
    block_id: str | None = None
    paragraph_no: int | None = Field(default=None, ge=1)
    selected_text: str | None = None
    selector_type: str | None = None
    selector_payload: dict[str, Any] = Field(default_factory=dict)


class CreateNoteRequest(BaseModel):
    anchor: NoteAnchorPayload
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=20000)


class UpdateNoteRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=20000)

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateNoteRequest":
        if self.title is None and self.content is None:
            raise ValueError("title 和 content 至少传一个。")
        return self


class NoteAnchorItem(BaseModel):
    id: str
    anchor_type: AnchorType
    page_no: int | None = None
    block_id: str | None = None
    paragraph_no: int | None = None
    selected_text: str | None = None
    selector_type: str
    selector_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class NoteItemResponse(BaseModel):
    id: str
    asset_id: str
    user_id: str
    title: str | None = None
    content: str
    anchor: NoteAnchorItem
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    asset_id: str
    total: int
    anchor_type: AnchorType | None = None
    notes: list[NoteItemResponse] = Field(default_factory=list)


class NoteDeleteResponse(BaseModel):
    note_id: str
    deleted: bool
