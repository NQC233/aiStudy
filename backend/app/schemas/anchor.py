from typing import Any

from pydantic import BaseModel, Field


class AssetAnchorPreviewRequest(BaseModel):
    page_no: int = Field(ge=1)
    selected_text: str = Field(min_length=1)
    block_id: str | None = None
    paragraph_no: int | None = Field(default=None, ge=1)
    selector_type: str = "block"
    selector_payload: dict[str, Any] = Field(default_factory=dict)


class AssetAnchorPreviewResponse(BaseModel):
    asset_id: str
    page_no: int
    block_id: str
    paragraph_no: int | None = None
    selected_text: str
    selector_type: str = "block"
    selector_payload: dict[str, Any] = Field(default_factory=dict)
