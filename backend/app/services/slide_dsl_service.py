from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.presentation import Presentation
from app.schemas.slide_dsl import (
    AssetSlidesResponse,
    MustPassReport,
    QualityScoreReport,
    ShadowEvaluationReport,
    SlideBlock,
    SlideCitation,
    SlideFixLog,
    SlideGenerationMeta,
    SlidePageDsl,
    SlidePlaybackPlan,
    SlideTtsManifest,
    SlidesDslPayload,
)
from app.schemas.slide_lesson_plan import AssetLessonPlanPayload, LessonPlanStage
from app.services.llm_service import (
    LLMConfigurationError,
    LLMRequestError,
    generate_slides_stage_copy,
)
from app.services.slide_fix_service import repair_low_quality_pages
from app.services.slide_dsl_compiler_service import compile_markdown_draft_to_slides_dsl
from app.services.slide_markdown_service import build_slide_markdown_draft
from app.services.slide_outline_service import build_slide_outline
from app.services.slide_playback_service import (
    build_playback_plan_from_slides,
    build_tts_manifest_placeholders,
    resolve_tts_status,
)
from app.services.slide_quality_service import (
    evaluate_slides_quality,
    validate_slides_must_pass,
)

SlidesStrategy = Literal["template", "llm"]
SlidesBuilder = Callable[[AssetLessonPlanPayload], SlidesDslPayload]


def build_slides_dsl(lesson_plan: AssetLessonPlanPayload) -> SlidesDslPayload:
    outline = build_slide_outline(lesson_plan)
    draft = build_slide_markdown_draft(outline)
    return compile_markdown_draft_to_slides_dsl(lesson_plan, draft)


def _build_slides_dsl_by_strategy(
    lesson_plan: AssetLessonPlanPayload,
    strategy: SlidesStrategy,
    llm_builder: SlidesBuilder,
) -> SlidesDslPayload:
    if strategy == "llm":
        return llm_builder(lesson_plan)
    return build_slides_dsl(lesson_plan)


def build_slides_dsl_via_llm(lesson_plan: AssetLessonPlanPayload) -> SlidesDslPayload:
    slides_dsl = build_slides_dsl(lesson_plan)
    for page in slides_dsl.pages:
        title_block = next((b for b in page.blocks if b.block_type == "title"), None)
        note_block = next((b for b in page.blocks if b.block_type == "speaker_note"), None)
        evidence_block = next((b for b in page.blocks if b.block_type == "evidence"), None)
        key_points_block = next((b for b in page.blocks if b.block_type == "key_points"), None)
        if not title_block or not note_block or not evidence_block:
            continue
        llm_copy = generate_slides_stage_copy(
            stage=page.stage,
            title=title_block.content,
            goal="",
            script=note_block.content,
            evidence_quotes=evidence_block.items,
        )
        title_block.content = llm_copy["title"]
        note_block.content = llm_copy["script"]
        evidence_block.items = [llm_copy["evidence"]]
        if key_points_block and llm_copy.get("goal"):
            key_points_block.items = [
                llm_copy["goal"],
                *[item for item in key_points_block.items if item][:2],
            ][:4]
    return slides_dsl


def is_legacy_slides_dsl_payload(slides_dsl_payload: dict | None) -> bool:
    if not isinstance(slides_dsl_payload, dict):
        return True
    schema_version = slides_dsl_payload.get("schema_version")
    return schema_version != "2"


def build_slides_dsl_with_strategy(
    lesson_plan: AssetLessonPlanPayload,
    strategy: SlidesStrategy,
    llm_enabled: bool,
    shadow_enabled: bool,
    llm_builder: SlidesBuilder | None = None,
) -> tuple[SlidesDslPayload, SlideGenerationMeta, ShadowEvaluationReport]:
    llm_builder_impl = llm_builder or build_slides_dsl_via_llm
    requested: SlidesStrategy = (
        strategy if strategy in {"template", "llm"} else "template"
    )
    applied: SlidesStrategy = requested
    fallback_used = False
    fallback_reason: str | None = None
    shadow_report = ShadowEvaluationReport(enabled=shadow_enabled, status="skipped")

    if requested == "llm" and not llm_enabled:
        applied = "template"
        fallback_used = True
        fallback_reason = "llm_disabled"

    if requested == "llm" and llm_enabled:
        try:
            slides_dsl = _build_slides_dsl_by_strategy(
                lesson_plan,
                applied,
                llm_builder=llm_builder_impl,
            )
        except (
            LLMConfigurationError,
            LLMRequestError,
            ValueError,
            RuntimeError,
        ) as exc:
            slides_dsl = build_slides_dsl(lesson_plan)
            applied = "template"
            fallback_used = True
            fallback_reason = "llm_generation_failed"
            shadow_report = ShadowEvaluationReport(
                enabled=shadow_enabled,
                status="failed",
                error_message=str(exc)[:500],
            )
    else:
        slides_dsl = _build_slides_dsl_by_strategy(
            lesson_plan,
            applied,
            llm_builder=llm_builder_impl,
        )
    generation_meta = SlideGenerationMeta(
        requested_strategy=requested,
        applied_strategy=applied,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )

    if not shadow_enabled:
        shadow_report = ShadowEvaluationReport(
            enabled=False,
            status="skipped",
            skip_reason="disabled",
        )
        return slides_dsl, generation_meta, shadow_report

    if not llm_enabled:
        shadow_report = ShadowEvaluationReport(
            enabled=True,
            status="skipped",
            skip_reason="llm_disabled",
        )
        return slides_dsl, generation_meta, shadow_report

    if shadow_report.status == "failed":
        return slides_dsl, generation_meta, shadow_report

    try:
        if applied == "llm":
            baseline_dsl = build_slides_dsl(lesson_plan)
            candidate_dsl = slides_dsl
        else:
            baseline_dsl = slides_dsl
            candidate_dsl = llm_builder_impl(lesson_plan)

        baseline_score = evaluate_slides_quality(baseline_dsl).overall_score
        candidate_score = evaluate_slides_quality(candidate_dsl).overall_score
        shadow_report = ShadowEvaluationReport(
            enabled=True,
            status="completed",
            baseline_overall_score=baseline_score,
            candidate_overall_score=candidate_score,
            score_delta=round(candidate_score - baseline_score, 2),
        )
    except (LLMConfigurationError, LLMRequestError, ValueError, RuntimeError) as exc:
        shadow_report = ShadowEvaluationReport(
            enabled=True,
            status="failed",
            error_message=str(exc)[:500],
        )

    return slides_dsl, generation_meta, shadow_report


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset


def run_asset_slides_dsl_pipeline(
    db: Session, asset_id: str, strategy: SlidesStrategy | str = "template"
) -> dict[str, str | int | float]:
    asset = _require_asset(db, asset_id)
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id).with_for_update()
    ).first()
    if presentation is None or not presentation.lesson_plan:
        raise RuntimeError("当前资产缺少 lesson_plan，无法生成 slides DSL。")

    lesson_plan = AssetLessonPlanPayload.model_validate(presentation.lesson_plan)
    slides_dsl, generation_meta, shadow_report = build_slides_dsl_with_strategy(
        lesson_plan,
        strategy="llm" if strategy == "llm" else "template",
        llm_enabled=settings.slides_llm_enabled,
        shadow_enabled=settings.slides_shadow_eval_enabled,
    )

    must_pass_report = validate_slides_must_pass(slides_dsl)
    quality_report = evaluate_slides_quality(slides_dsl)
    fix_logs = []

    if quality_report.low_quality_pages:
        slides_dsl, fix_logs = repair_low_quality_pages(
            slides_dsl,
            lesson_plan,
            quality_report,
        )
        quality_report = evaluate_slides_quality(slides_dsl)

    presentation.slides_dsl = slides_dsl.model_dump(mode="json")
    presentation.tts_manifest = build_tts_manifest_placeholders(slides_dsl).model_dump(
        mode="json"
    )
    presentation.playback_plan = build_playback_plan_from_slides(slides_dsl).model_dump(
        mode="json"
    )
    presentation.dsl_quality_report = {
        "must_pass": must_pass_report.model_dump(mode="json"),
        "quality": quality_report.model_dump(mode="json"),
        "generation_meta": generation_meta.model_dump(mode="json"),
        "shadow_report": shadow_report.model_dump(mode="json"),
    }
    presentation.dsl_fix_logs = [item.model_dump(mode="json") for item in fix_logs]
    presentation.status = "ready"
    presentation.error_meta = {}
    asset.slides_status = "ready"
    db.commit()

    return {
        "asset_id": asset_id,
        "status": "ready",
        "page_count": len(slides_dsl.pages),
        "overall_score": quality_report.overall_score,
        "fixed_page_count": len(fix_logs),
        "strategy_applied": generation_meta.applied_strategy,
        "shadow_status": shadow_report.status,
    }


def get_asset_slides_snapshot(db: Session, asset_id: str) -> AssetSlidesResponse:
    asset = _require_asset(db, asset_id)
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id)
    ).first()
    if presentation is None:
        return AssetSlidesResponse(asset_id=asset.id, slides_status=asset.slides_status)

    slides_dsl = (
        SlidesDslPayload.model_validate(presentation.slides_dsl)
        if presentation.slides_dsl
        else None
    )
    must_pass_report = None
    quality_report = None
    generation_meta = SlideGenerationMeta()
    shadow_report = ShadowEvaluationReport()
    quality_payload = presentation.dsl_quality_report or {}
    if isinstance(quality_payload, dict):
        must_pass_data = quality_payload.get("must_pass")
        quality_data = quality_payload.get("quality")
        generation_meta_data = quality_payload.get("generation_meta")
        shadow_report_data = quality_payload.get("shadow_report")
        if isinstance(must_pass_data, dict):
            must_pass_report = MustPassReport.model_validate(must_pass_data)
        if isinstance(quality_data, dict):
            quality_report = QualityScoreReport.model_validate(quality_data)
        if isinstance(generation_meta_data, dict):
            generation_meta = SlideGenerationMeta.model_validate(generation_meta_data)
        if isinstance(shadow_report_data, dict):
            shadow_report = ShadowEvaluationReport.model_validate(shadow_report_data)

    fix_logs = []
    for item in presentation.dsl_fix_logs or []:
        if isinstance(item, dict):
            fix_logs.append(SlideFixLog.model_validate(item))

    tts_manifest = SlideTtsManifest()
    playback_plan = SlidePlaybackPlan()

    presentation_tts_manifest = getattr(presentation, "tts_manifest", None)
    if isinstance(presentation_tts_manifest, dict):
        tts_manifest = SlideTtsManifest.model_validate(presentation_tts_manifest)
    elif slides_dsl is not None:
        tts_manifest = build_tts_manifest_placeholders(slides_dsl)

    presentation_playback_plan = getattr(presentation, "playback_plan", None)
    if isinstance(presentation_playback_plan, dict):
        playback_plan = SlidePlaybackPlan.model_validate(presentation_playback_plan)
    elif slides_dsl is not None:
        playback_plan = build_playback_plan_from_slides(slides_dsl)

    tts_status = resolve_tts_status([item.status for item in tts_manifest.pages])
    playback_status = "ready" if playback_plan.pages else "not_ready"

    return AssetSlidesResponse(
        asset_id=asset.id,
        slides_status=asset.slides_status,
        schema_version=slides_dsl.schema_version if slides_dsl is not None else None,
        tts_status=tts_status,
        playback_status=playback_status,
        auto_page_supported=playback_status == "ready",
        slides_dsl=slides_dsl,
        must_pass_report=must_pass_report,
        quality_report=quality_report,
        fix_logs=fix_logs,
        generation_meta=generation_meta,
        shadow_report=shadow_report,
        tts_manifest=tts_manifest,
        playback_plan=playback_plan,
    )


def ensure_asset_slides_schema_up_to_date(
    db: Session,
    asset_id: str,
) -> tuple[Asset, bool, str]:
    from app.services.slide_lesson_plan_service import enqueue_asset_lesson_plan_rebuild

    asset = _require_asset(db, asset_id)
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id)
    ).first()
    if presentation is None:
        return asset, False, "presentation 不存在，跳过 schema 升级检查。"
    if not is_legacy_slides_dsl_payload(presentation.slides_dsl):
        return asset, False, "slides_dsl 已是 v2，无需重建。"
    rebuilt_asset, should_enqueue, _ = enqueue_asset_lesson_plan_rebuild(db, asset_id)
    if should_enqueue:
        return rebuilt_asset, True, "检测到旧版 slides_dsl，已自动触发 schema 升级重建。"
    return rebuilt_asset, False, "检测到旧版 slides_dsl，但当前已有重建任务在执行。"
