from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MindmapNodeItem(BaseModel):
    id: str
    parent_id: str | None = None
    node_key: str
    parent_key: str | None = None
    title: str
    summary: str | None = None
    level: int
    order: int
    page_no: int | None = None
    paragraph_ref: str | None = None
    section_path: list[str] = Field(default_factory=list)
    block_ids: list[str] = Field(default_factory=list)
    selector_payload: dict[str, Any] = Field(default_factory=dict)


class MindmapSnapshot(BaseModel):
    id: str
    asset_id: str
    version: int
    status: str
    root_node_key: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    nodes: list[MindmapNodeItem] = Field(default_factory=list)


class AssetMindmapResponse(BaseModel):
    asset_id: str
    mindmap_status: str
    mindmap: MindmapSnapshot | None = None


class AssetMindmapRebuildResponse(BaseModel):
    asset_id: str
    mindmap_status: str
    message: str
