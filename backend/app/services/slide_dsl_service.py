from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.presentation import Presentation
from app.schemas.slide_dsl import (
    AssetSlidesResponse,
    MustPassReport,
    QualityScoreReport,
    RuntimeRenderedPage,
    ShadowEvaluationReport,
    SlideFixLog,
    SlideGenerationMeta,
    SlidePlaybackPlan,
    SlidesRuntimeBundle,
    SlideTtsManifest,
    SlidesDslPayload,
)
from app.services.slide_playback_service import (
    build_playback_plan_from_slides,
    build_tts_manifest_placeholders,
    resolve_tts_status,
)


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset


def _build_runtime_bundle_from_slides_dsl(
    slides_dsl: SlidesDslPayload | None,
) -> SlidesRuntimeBundle | None:
    if slides_dsl is None:
        return None

    pages: list[RuntimeRenderedPage] = []
    for page in slides_dsl.pages:
        title = next(
            (block.content.strip() for block in page.blocks if block.block_type == "title" and block.content.strip()),
            page.slide_key,
        )
        bullet_items = [
            item
            for block in page.blocks
            if block.block_type in {"key_points", "evidence", "flow"}
            for item in block.items[:4]
            if isinstance(item, str) and item.strip()
        ]
        fallback_text = next(
            (
                block.content.strip()
                for block in page.blocks
                if block.block_type not in {"title", "speaker_note"} and block.content.strip()
            ),
            "",
        )
        body_html = "".join(f"<li>{item}</li>" for item in bullet_items)
        if not body_html and fallback_text:
            body_html = f"<p>{fallback_text}</p>"
        elif body_html:
            body_html = f"<ul>{body_html}</ul>"
        else:
            body_html = "<p>Slides content is being migrated to the HTML runtime bundle.</p>"

        pages.append(
            RuntimeRenderedPage(
                page_id=page.slide_key,
                html=(
                    "<section class=\"slide-runtime-page\">"
                    f"<h1>{title}</h1>"
                    f"{body_html}"
                    "</section>"
                ),
                css=(
                    ".slide-runtime-page{width:100%;height:100%;box-sizing:border-box;"
                    "padding:72px 88px;background:linear-gradient(180deg,#fffaf0 0%,#fff 100%);"
                    "color:#1f2937;font-family:Inter,system-ui,sans-serif;}"
                    ".slide-runtime-page h1{margin:0 0 24px;font-size:42px;line-height:1.1;}"
                    ".slide-runtime-page p,.slide-runtime-page li{font-size:24px;line-height:1.55;}"
                    ".slide-runtime-page ul{margin:0;padding-left:28px;display:grid;gap:12px;}"
                ),
                asset_refs=[],
                render_meta={
                    "source": "legacy_slides_dsl_adapter",
                    "page_type": page.page_type,
                    "layout_hint": page.layout_hint,
                    "visual_tone": page.visual_tone,
                },
            )
        )

    return SlidesRuntimeBundle(page_count=len(pages), pages=pages)


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
    runtime_bundle_payload = getattr(presentation, "runtime_bundle", None)
    if isinstance(runtime_bundle_payload, dict):
        runtime_bundle = SlidesRuntimeBundle.model_validate(runtime_bundle_payload)
    else:
        runtime_bundle = _build_runtime_bundle_from_slides_dsl(slides_dsl)
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
    playback_status = "ready" if runtime_bundle and runtime_bundle.pages else "not_ready"

    return AssetSlidesResponse(
        asset_id=asset.id,
        slides_status=asset.slides_status,
        schema_version=slides_dsl.schema_version if slides_dsl is not None else None,
        tts_status=tts_status,
        playback_status=playback_status,
        auto_page_supported=playback_status == "ready",
        slides_dsl=None,
        runtime_bundle=runtime_bundle,
        must_pass_report=must_pass_report,
        quality_report=quality_report,
        fix_logs=fix_logs,
        generation_meta=generation_meta,
        shadow_report=shadow_report,
        tts_manifest=tts_manifest,
        playback_plan=playback_plan,
    )
