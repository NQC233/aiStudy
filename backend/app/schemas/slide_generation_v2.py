from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.slide_dsl import SlidesRuntimeBundle


class SlideGenerationArtifacts(BaseModel):
    asset_id: str
    slides_status: str
    analysis_pack: dict[str, Any] = Field(default_factory=dict)
    visual_asset_catalog: list[dict[str, Any]] = Field(default_factory=list)
    presentation_plan: dict[str, Any] = Field(default_factory=dict)
    scene_specs: list[dict[str, Any]] = Field(default_factory=list)
    rendered_slide_pages: list[dict[str, Any]] = Field(default_factory=list)
    runtime_bundle: SlidesRuntimeBundle
    error_meta: dict[str, Any] = Field(default_factory=dict)
