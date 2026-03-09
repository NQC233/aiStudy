from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SelectedAnchorPayload(BaseModel):
    page_no: int = Field(ge=1)
    block_id: str | None = None
    paragraph_no: int | None = Field(default=None, ge=1)
    selected_text: str | None = None
    selector_type: str | None = None
    selector_payload: dict[str, Any] = Field(default_factory=dict)


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatSessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    user_id: str
    title: str
    message_count: int = 0
    created_at: datetime


class ChatMessageCitationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    citation_id: str
    chunk_id: str
    score: float
    page_start: int | None = None
    page_end: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None
    section_path: list[str] = Field(default_factory=list)
    block_ids: list[str] = Field(default_factory=list)
    quote_text: str


class ChatMessageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    message_type: str
    content: str
    selection_anchor_payload: dict[str, Any] | None = None
    citations: list[ChatMessageCitationItem] = Field(default_factory=list)
    created_at: datetime


class ChatSessionMessagesResponse(BaseModel):
    session_id: str
    asset_id: str
    messages: list[ChatMessageItem] = Field(default_factory=list)


class ChatMessageCreateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    selected_anchor: SelectedAnchorPayload | None = None
    top_k: int = Field(default=6, ge=1, le=20)


class ChatMessageCreateResponse(BaseModel):
    session_id: str
    question_message_id: str
    answer_message_id: str
    answer: str
    citations: list[ChatMessageCitationItem] = Field(default_factory=list)
