from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class SlideCitation(BaseModel):
    page_no: int
    block_ids: list[str] = Field(default_factory=list)
    quote: str


class SlideBlock(BaseModel):
    block_type: str
    content: str


class SlidePageDsl(BaseModel):
    slide_key: str
    stage: str
    template_type: str
    animation_preset: str
    blocks: list[SlideBlock] = Field(default_factory=list)
    citations: list[SlideCitation] = Field(default_factory=list)


class SlidesDslPayload(BaseModel):
    asset_id: str
    version: int
    generated_at: str
    pages: list[SlidePageDsl] = Field(default_factory=list)


class MustPassIssue(BaseModel):
    page_index: int
    field: str
    code: str
    message: str


class MustPassReport(BaseModel):
    passed: bool
    issues: list[MustPassIssue] = Field(default_factory=list)


class PageQualityScore(BaseModel):
    page_index: int
    slide_key: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class QualityScoreReport(BaseModel):
    overall_score: float
    page_scores: list[PageQualityScore] = Field(default_factory=list)
    low_quality_pages: list[int] = Field(default_factory=list)


class SlideFixLog(BaseModel):
    page_index: int
    slide_key: str
    before_score: float
    after_score: float
    reason: str


class SlideGenerationMeta(BaseModel):
    requested_strategy: Literal["template", "llm"] = "template"
    applied_strategy: Literal["template", "llm"] = "template"
    fallback_used: bool = False
    fallback_reason: str | None = None


class ShadowEvaluationReport(BaseModel):
    enabled: bool = False
    target_strategy: Literal["llm"] = "llm"
    status: Literal["skipped", "completed", "failed"] = "skipped"
    skip_reason: str | None = None
    error_message: str | None = None
    candidate_overall_score: float | None = None
    baseline_overall_score: float | None = None
    score_delta: float | None = None


class SlidesDslSnapshot(BaseModel):
    slides_dsl: SlidesDslPayload
    must_pass_report: MustPassReport
    quality_report: QualityScoreReport
    fix_logs: list[SlideFixLog] = Field(default_factory=list)
    generation_meta: SlideGenerationMeta = Field(default_factory=SlideGenerationMeta)
    shadow_report: ShadowEvaluationReport = Field(
        default_factory=ShadowEvaluationReport
    )
    updated_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)


class AssetSlidesResponse(BaseModel):
    asset_id: str
    slides_status: str
    slides_dsl: SlidesDslPayload | None = None
    must_pass_report: MustPassReport | None = None
    quality_report: QualityScoreReport | None = None
    fix_logs: list[SlideFixLog] = Field(default_factory=list)
    generation_meta: SlideGenerationMeta = Field(default_factory=SlideGenerationMeta)
    shadow_report: ShadowEvaluationReport = Field(
        default_factory=ShadowEvaluationReport
    )
