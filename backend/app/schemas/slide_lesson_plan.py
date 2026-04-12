from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_REQUIRED_STAGES = ["problem", "method", "mechanism", "experiment", "conclusion"]
SlideGenerationStrategy = Literal["template", "llm"]


class LessonPlanEvidenceAnchor(BaseModel):
    page_no: int
    block_ids: list[str] = Field(default_factory=list)
    paragraph_ref: str | None = None
    quote: str
    selector_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_anchor(self) -> "LessonPlanEvidenceAnchor":
        if self.page_no < 1:
            raise ValueError("page_no 必须 >= 1")
        if not self.block_ids:
            raise ValueError("block_ids 不能为空")
        if not self.selector_payload:
            raise ValueError("selector_payload 不能为空")
        return self


class LessonPlanStage(BaseModel):
    stage: str
    title: str
    goal: str
    script: str
    evidence_anchors: list[LessonPlanEvidenceAnchor] = Field(default_factory=list)
    source_section_hints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stage(self) -> "LessonPlanStage":
        if not self.evidence_anchors:
            raise ValueError("每个阶段至少需要一个证据锚点")
        return self


class AssetLessonPlanPayload(BaseModel):
    asset_id: str
    version: int
    generated_at: str
    stages: list[LessonPlanStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stages(self) -> "AssetLessonPlanPayload":
        stage_names = [stage.stage for stage in self.stages]
        if stage_names != _REQUIRED_STAGES:
            raise ValueError(
                "lesson_plan 必须覆盖 problem/method/mechanism/experiment/conclusion"
            )
        return self


class LessonPlanStageSummary(BaseModel):
    stage: str
    title: str
    anchor_count: int


class PresentationSnapshot(BaseModel):
    id: str
    asset_id: str
    version: int
    status: str
    lesson_plan: AssetLessonPlanPayload | None = None
    error_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AssetLessonPlanResponse(BaseModel):
    asset_id: str
    slides_status: str
    presentation: PresentationSnapshot | None = None
    summary: list[LessonPlanStageSummary] = Field(default_factory=list)


class AssetLessonPlanRebuildResponse(BaseModel):
    asset_id: str
    slides_status: str
    message: str
    strategy: SlideGenerationStrategy = "llm"


class AssetLessonPlanRebuildRequest(BaseModel):
    strategy: SlideGenerationStrategy = "llm"
