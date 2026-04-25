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
    content: str = ""
    items: list[str] = Field(default_factory=list)
    svg_content: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class SlideAnimation(BaseModel):
    animation_type: Literal[
        "stagger_reveal",
        "focus_emphasis",
        "compare_switch",
        "flow_step",
    ]
    target_block_type: str
    cue_key: str


class SlidePageDsl(BaseModel):
    slide_key: str
    stage: str
    page_type: str = "topic"
    layout_hint: str = "hero-left"
    director_source: Literal["rule", "llm"] = "rule"
    visual_tone: Literal["editorial", "technical", "spotlight", "warm"] = "technical"
    template_type: str
    animation_preset: str
    animations: list[SlideAnimation] = Field(default_factory=list)
    blocks: list[SlideBlock] = Field(default_factory=list)
    citations: list[SlideCitation] = Field(default_factory=list)


class SlidesDslPayload(BaseModel):
    schema_version: Literal["2"] = "2"
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


class SlideTtsManifestItem(BaseModel):
    slide_key: str
    audio_url: str | None = None
    duration_ms: int | None = None
    status: Literal["pending", "processing", "ready", "failed"] = "pending"
    error_message: str | None = None
    retry_meta: dict[str, Any] | None = None


class SlideTtsManifest(BaseModel):
    pages: list[SlideTtsManifestItem] = Field(default_factory=list)


class SlideCueItem(BaseModel):
    block_id: str
    start_ms: int
    end_ms: int
    animation: str


class SlidePlaybackPagePlan(BaseModel):
    slide_key: str
    start_ms: int
    end_ms: int
    duration_ms: int
    cues: list[SlideCueItem] = Field(default_factory=list)


class SlidePlaybackPlan(BaseModel):
    total_duration_ms: int = 0
    pages: list[SlidePlaybackPagePlan] = Field(default_factory=list)


class RuntimeRenderedPage(BaseModel):
    page_id: str
    html: str
    css: str
    asset_refs: list[dict[str, Any]] = Field(default_factory=list)
    render_meta: dict[str, Any] = Field(default_factory=dict)


class SlidesRuntimeBundleValidationSummary(BaseModel):
    status: Literal["not_ready", "partial_ready", "ready"] = "not_ready"
    page_count: int = 0
    playable_page_count: int = 0
    failed_page_numbers: list[int] = Field(default_factory=list)


class SlidesRuntimeBundle(BaseModel):
    page_count: int = 0
    pages: list[RuntimeRenderedPage] = Field(default_factory=list)
    playable_page_count: int = 0
    failed_page_numbers: list[int] = Field(default_factory=list)
    validation_summary: SlidesRuntimeBundleValidationSummary = Field(
        default_factory=SlidesRuntimeBundleValidationSummary
    )
    deck_meta: dict[str, Any] = Field(default_factory=dict)
    generation_meta: dict[str, Any] = Field(default_factory=dict)


class AssetSlidesRebuildMeta(BaseModel):
    from_stage: Literal["full", "scene", "html", "runtime"] = "full"
    requested_page_numbers: list[int] = Field(default_factory=list)
    effective_page_numbers: list[int] = Field(default_factory=list)
    failed_only: bool = False
    reused_layers: list[str] = Field(default_factory=list)
    rebuilt_layers: list[str] = Field(default_factory=list)


class AssetSlidesRebuildRequest(BaseModel):
    from_stage: Literal["full", "scene", "html", "runtime"] = "full"
    page_numbers: list[int] = Field(default_factory=list)
    failed_only: bool = False
    reuse_analysis_pack: bool = True
    reuse_presentation_plan: bool = True
    debug_target: Literal["analysis", "plan", "scene", "html", "full"] = "full"


class AssetSlidesResponse(BaseModel):
    asset_id: str
    slides_status: str
    schema_version: str | None = None
    rebuilding: bool = False
    rebuild_reason: str | None = None
    rebuild_meta: AssetSlidesRebuildMeta | None = None
    tts_status: Literal[
        "not_generated",
        "processing",
        "ready",
        "failed",
        "partial",
    ] = "not_generated"
    playback_status: Literal["not_ready", "partial_ready", "ready"] = "not_ready"
    auto_page_supported: bool = False
    playable_page_count: int = 0
    failed_page_numbers: list[int] = Field(default_factory=list)
    slides_dsl: SlidesDslPayload | None = None
    runtime_bundle: SlidesRuntimeBundle | None = None
    must_pass_report: MustPassReport | None = None
    quality_report: QualityScoreReport | None = None
    fix_logs: list[SlideFixLog] = Field(default_factory=list)
    generation_meta: SlideGenerationMeta = Field(default_factory=SlideGenerationMeta)
    shadow_report: ShadowEvaluationReport = Field(
        default_factory=ShadowEvaluationReport
    )
    tts_manifest: SlideTtsManifest = Field(default_factory=SlideTtsManifest)
    playback_plan: SlidePlaybackPlan = Field(default_factory=SlidePlaybackPlan)


class AssetSlideTtsEnsureRequest(BaseModel):
    page_index: int = 0
    prefetch_next: bool = True


class AssetSlideTtsEnsureResponse(BaseModel):
    asset_id: str
    page_index: int
    enqueued_slide_keys: list[str] = Field(default_factory=list)
    tts_status: Literal[
        "not_generated",
        "processing",
        "ready",
        "failed",
        "partial",
    ] = "not_generated"
    message: str


class AssetSlideTtsRetryNextRequest(BaseModel):
    current_page_index: int = 0


class AssetSlideTtsRetryNextResponse(BaseModel):
    asset_id: str
    current_page_index: int
    next_slide_key: str | None = None
    enqueued_slide_keys: list[str] = Field(default_factory=list)
    tts_status: Literal[
        "not_generated",
        "processing",
        "ready",
        "failed",
        "partial",
    ] = "not_generated"
    message: str
