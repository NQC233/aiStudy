from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.models.asset import Asset
from app.models.presentation import Presentation
from app.schemas.slide_generation_v2 import SlideGenerationArtifacts
from app.services.asset_reader_service import get_asset_parsed_document
from app.services.llm_service import describe_visual_asset
from app.services.retrieval_service import search_asset_chunks
from app.services.slide_analysis_service import build_asset_slide_analysis_pack
from app.services.slide_html_authoring_service import render_slide_page
from app.services.slide_planning_service import build_presentation_plan
from app.services.slide_planning_service import build_plan_fallback
from app.services.slide_planning_service import _validate_presentation_plan
from app.services.slide_runtime_bundle_service import build_runtime_bundle
from app.services.slide_scene_service import build_scene_specs
from app.services.slide_visual_asset_service import build_visual_asset_cards


DEBUG_TARGETS = {"analysis", "plan", "scene", "html", "full"}


def _require_asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到对应的学习资产。",
        )
    return asset


def _get_or_create_presentation(db: Session, asset_id: str) -> Presentation:
    presentation = db.scalars(
        select(Presentation).where(Presentation.asset_id == asset_id)
    ).first()
    if presentation is not None:
        return presentation

    presentation = Presentation(asset_id=asset_id)
    db.add(presentation)
    return presentation


def _collect_visual_assets(parsed_payload: dict[str, Any]) -> list[dict[str, object]]:
    assets = parsed_payload.get("assets", {})
    images = assets.get("images", []) if isinstance(assets, dict) else []
    tables = assets.get("tables", []) if isinstance(assets, dict) else []
    collected: list[dict[str, object]] = []
    for asset in [*images, *tables]:
        if isinstance(asset, dict):
            collected.append(asset)
    return collected


def _default_parsed_payload_loader(db: Session, asset_id: str) -> dict[str, Any]:
    parsed_document = get_asset_parsed_document(db, asset_id)
    if parsed_document.parsed_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产还没有可用的 parsed_json，暂时无法生成 slides。",
        )
    return parsed_document.parsed_json.model_dump(mode="json")


def _default_analysis_builder(
    db: Session,
    *,
    asset_id: str,
    search_func: Callable[..., Any] = search_asset_chunks,
) -> dict[str, Any]:
    analysis_pack = build_asset_slide_analysis_pack(
        asset_id,
        search_func=lambda asset_id, query, top_k, rewrite_query, strategy: search_func(
            db,
            asset_id,
            query,
            top_k,
            rewrite_query,
            strategy,
        ),
    )
    return _coerce_analysis_pack(analysis_pack)


def _default_visual_asset_builder(
    assets: list[dict[str, object]],
) -> list[dict[str, object]]:
    return build_visual_asset_cards(assets, describe_asset=describe_visual_asset)


def _coerce_analysis_pack(analysis_result: Any) -> dict[str, Any]:
    if isinstance(analysis_result, dict):
        return analysis_result
    if hasattr(analysis_result, "__dict__"):
        return {
            key: value
            for key, value in vars(analysis_result).items()
            if not key.startswith("_")
        }
    return {}


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_safe(item) for item in value]
    return value


def _scene_fallback_from_plan(page: dict[str, Any]) -> dict[str, object]:
    narrative_goal = str(page.get("narrative_goal", "Paper Overview")).strip() or "Paper Overview"
    candidate_assets = page.get("candidate_assets")
    asset_bindings: list[dict[str, str]] = []
    if isinstance(candidate_assets, list):
        for asset_id in candidate_assets[:1]:
            if isinstance(asset_id, str) and asset_id.strip():
                asset_bindings.append({"asset_id": asset_id})
    return {
        "page_id": page.get("page_id", "page-1"),
        "title": narrative_goal,
        "summary_line": narrative_goal,
        "layout_strategy": "hero-visual-right" if asset_bindings else "hero-text",
        "content_blocks": [],
        "citations": [],
        "asset_bindings": asset_bindings,
        "animation_plan": {"type": page.get("animation_intent", "soft_intro")},
        "speaker_note_seed": narrative_goal,
    }


def _plan_fallback_from_inputs(
    analysis_pack: dict[str, Any],
    visual_asset_catalog: list[dict[str, object]],
) -> dict[str, object]:
    return build_plan_fallback(analysis_pack, visual_asset_catalog)


def _build_validated_plan(
    active_plan_builder: Callable[..., dict[str, object]],
    analysis_pack: dict[str, Any],
    visual_asset_catalog: list[dict[str, object]],
) -> dict[str, Any]:
    plan = _to_json_safe(active_plan_builder(analysis_pack, visual_asset_catalog))
    _validate_presentation_plan(plan, analysis_pack, _to_json_safe(visual_asset_catalog))
    return plan


def _extract_plan_debug(plan: dict[str, Any]) -> dict[str, Any]:
    debug = plan.get("_debug")
    if isinstance(debug, dict):
        return debug
    return {}


def _strip_plan_debug(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "_debug"}


def _extract_scene_debug(scene_spec: dict[str, Any]) -> dict[str, Any]:
    debug = scene_spec.get("_debug")
    if isinstance(debug, dict):
        return debug
    content_blocks = scene_spec.get("content_blocks")
    citations = scene_spec.get("citations")
    asset_bindings = scene_spec.get("asset_bindings")
    content_blocks_count = len(content_blocks) if isinstance(content_blocks, list) else 0
    citations_count = len(citations) if isinstance(citations, list) else 0
    asset_bindings_count = len(asset_bindings) if isinstance(asset_bindings, list) else 0
    return {
        "scene_source": "generated",
        "is_empty_scene": content_blocks_count == 0 and citations_count == 0,
        "content_blocks_count": content_blocks_count,
        "citations_count": citations_count,
        "asset_bindings_count": asset_bindings_count,
    }


def _strip_scene_debug(scene_spec: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in scene_spec.items() if key != "_debug"}


def _html_fallback_from_scene(scene_spec: dict[str, Any]) -> dict[str, object]:
    title = str(scene_spec.get("title", "Paper Overview")).strip() or "Paper Overview"
    summary_line = str(scene_spec.get("summary_line", "")).strip()
    content_html = f"<p>{summary_line}</p>" if summary_line else ""
    return {
        "page_id": scene_spec["page_id"],
        "html": f"<section class=\"slide-page\"><h1>{title}</h1>{content_html}</section>",
        "css": (
            ".slide-page{width:100%;height:100%;box-sizing:border-box;padding:72px 88px;"
            "background:#fff;color:#1f2937;font-family:Inter,system-ui,sans-serif;}"
            ".slide-page h1{margin:0 0 24px;font-size:42px;line-height:1.1;}"
            ".slide-page p{margin:0;font-size:24px;line-height:1.5;}"
        ),
        "asset_refs": scene_spec.get("asset_bindings", []),
        "render_meta": {"layout_strategy": scene_spec.get("layout_strategy", "")},
    }


def _build_empty_runtime_bundle() -> dict[str, object]:
    return {"page_count": 0, "pages": []}


def generate_asset_slides_runtime_bundle(
    db: Session,
    *,
    asset_id: str,
    parsed_payload: dict[str, Any] | None = None,
    parsed_payload_loader: Callable[[Session, str], dict[str, Any]] = _default_parsed_payload_loader,
    analysis_builder: Callable[..., Any] = _default_analysis_builder,
    search_func: Callable[..., Any] = search_asset_chunks,
    visual_asset_builder: Callable[..., list[dict[str, object]]] = _default_visual_asset_builder,
    plan_builder: Callable[..., dict[str, object]] = build_presentation_plan,
    scene_builder: Callable[..., list[dict[str, object]]] = build_scene_specs,
    html_renderer: Callable[..., dict[str, object]] = render_slide_page,
    llm_enabled: bool | None = None,
    llm_plan_builder: Callable[[dict[str, Any], list[dict[str, object]]], dict[str, object]] | None = None,
    llm_scene_builder: Callable[[dict[str, object], dict[str, Any], list[dict[str, object]]], list[dict[str, object]]] | None = None,
    llm_html_renderer: Callable[[dict[str, object]], dict[str, object]] | None = None,
    runtime_bundle_builder: Callable[..., dict[str, object]] = build_runtime_bundle,
    debug_target: str = "full",
) -> dict[str, Any]:
    normalized_debug_target = debug_target.strip().lower() if isinstance(debug_target, str) else "full"
    if normalized_debug_target not in DEBUG_TARGETS:
        raise ValueError(f"unsupported debug target: {debug_target}")

    asset = _require_asset(db, asset_id)
    presentation = _get_or_create_presentation(db, asset_id)
    presentation.status = "processing"
    asset.slides_status = "processing"
    db.commit()
    db.refresh(asset)
    parsed_payload = parsed_payload or parsed_payload_loader(db, asset_id)

    visual_assets = _collect_visual_assets(parsed_payload)
    analysis_result = analysis_builder(db, asset_id=asset_id, search_func=search_func)
    analysis_pack = _to_json_safe(_coerce_analysis_pack(analysis_result))
    visual_asset_catalog = visual_asset_builder(visual_assets)
    error_meta: dict[str, Any] = {
        "debug_target": normalized_debug_target,
        "plan_generation": [],
        "scene_generation": [],
        "html_generation": [],
    }
    should_use_llm = settings.slides_llm_enabled if llm_enabled is None else llm_enabled
    active_plan_builder = plan_builder
    active_scene_builder = scene_builder
    active_html_renderer = html_renderer
    if should_use_llm:
        if llm_plan_builder is not None:
            active_plan_builder = llm_plan_builder
        if llm_scene_builder is not None:
            active_scene_builder = lambda presentation_plan, **_kwargs: llm_scene_builder(
                presentation_plan,
                analysis_pack,
                visual_asset_catalog,
            )
        if llm_html_renderer is not None:
            active_html_renderer = llm_html_renderer

    presentation_plan: dict[str, Any] = {}
    scene_specs: list[dict[str, Any]] = []
    rendered_slide_pages: list[dict[str, Any]] = []
    runtime_bundle = _to_json_safe(_build_empty_runtime_bundle())

    if normalized_debug_target != "analysis":
        try:
            raw_plan = _build_validated_plan(active_plan_builder, analysis_pack, _to_json_safe(visual_asset_catalog))
            plan_debug = _extract_plan_debug(raw_plan)
            presentation_plan = _strip_plan_debug(raw_plan)
            pages = presentation_plan.get("pages") if isinstance(presentation_plan, dict) else []
            error_meta["plan_generation"].append(
                {
                    "status": "success",
                    "reason": "",
                    "fallback_used": False,
                    "planner_status": "success",
                    "planner_error": "",
                    "page_count": len(pages),
                    "plan_source": plan_debug.get("plan_source", "generated"),
                    "internal_fallback_used": bool(plan_debug.get("internal_fallback_used", False)),
                    "internal_error": str(plan_debug.get("internal_error", "")),
                    "raw_page_count": int(plan_debug.get("raw_page_count", len(pages)) or 0),
                    "validated_page_count": int(plan_debug.get("validated_page_count", len(pages)) or 0),
                }
            )
        except Exception as exc:
            presentation_plan = _to_json_safe(_plan_fallback_from_inputs(analysis_pack, _to_json_safe(visual_asset_catalog)))
            error_meta["plan_generation"].append(
                {
                    "status": "fallback",
                    "reason": str(exc),
                    "fallback_used": True,
                    "planner_status": "error",
                    "planner_error": str(exc),
                    "page_count": presentation_plan.get("page_count", 1),
                    "plan_source": "fallback",
                    "internal_fallback_used": False,
                    "internal_error": "",
                    "raw_page_count": 0,
                    "validated_page_count": int(presentation_plan.get("page_count", 1) or 0),
                }
            )

    if normalized_debug_target not in {"analysis", "plan"}:
        try:
            raw_scene_specs = _to_json_safe(
                active_scene_builder(
                    presentation_plan,
                    analysis_pack=analysis_pack,
                    visual_asset_catalog=_to_json_safe(visual_asset_catalog),
                )
            )
            scene_specs = [_strip_scene_debug(scene_spec) for scene_spec in raw_scene_specs]
            for scene_spec, raw_scene_spec in zip(scene_specs, raw_scene_specs, strict=False):
                scene_debug = _extract_scene_debug(raw_scene_spec)
                error_meta["scene_generation"].append(
                    {
                        "page_id": scene_spec.get("page_id", "unknown"),
                        "status": "success",
                        "reason": "",
                        "scene_source": scene_debug.get("scene_source", "generated"),
                        "is_empty_scene": bool(scene_debug.get("is_empty_scene", False)),
                        "content_blocks_count": int(scene_debug.get("content_blocks_count", 0) or 0),
                        "citations_count": int(scene_debug.get("citations_count", 0) or 0),
                        "asset_bindings_count": int(scene_debug.get("asset_bindings_count", 0) or 0),
                    }
                )
        except Exception as exc:
            fallback_pages = presentation_plan.get("pages", []) if isinstance(presentation_plan.get("pages"), list) else []
            scene_specs = [_scene_fallback_from_plan(page) for page in fallback_pages]
            for page in fallback_pages:
                error_meta["scene_generation"].append(
                    {
                        "page_id": page.get("page_id", "unknown"),
                        "status": "fallback",
                        "reason": str(exc),
                    }
                )

    if normalized_debug_target not in {"analysis", "plan", "scene"}:
        for scene_spec in scene_specs:
            try:
                rendered_slide_pages.append(_to_json_safe(active_html_renderer(scene_spec)))
                error_meta["html_generation"].append(
                    {
                        "page_id": scene_spec.get("page_id", "unknown"),
                        "status": "success",
                        "reason": "",
                    }
                )
            except Exception as exc:
                rendered_slide_pages.append(_to_json_safe(_html_fallback_from_scene(scene_spec)))
                error_meta["html_generation"].append(
                    {
                        "page_id": scene_spec.get("page_id", "unknown"),
                        "status": "fallback",
                        "reason": str(exc),
                    }
                )

        runtime_bundle = _to_json_safe(runtime_bundle_builder(rendered_slide_pages))

    presentation.analysis_pack = analysis_pack
    presentation.visual_asset_catalog = _to_json_safe(visual_asset_catalog)
    presentation.presentation_plan = presentation_plan
    presentation.scene_specs = scene_specs
    presentation.rendered_slide_pages = rendered_slide_pages
    presentation.runtime_bundle = runtime_bundle
    presentation.status = "ready"
    presentation.error_meta = error_meta
    asset.slides_status = "ready"
    db.commit()
    db.refresh(asset)

    artifacts = SlideGenerationArtifacts(
        asset_id=asset.id,
        slides_status=asset.slides_status,
        analysis_pack=analysis_pack,
        visual_asset_catalog=visual_asset_catalog,
        presentation_plan=presentation_plan,
        scene_specs=scene_specs,
        rendered_slide_pages=rendered_slide_pages,
        runtime_bundle=runtime_bundle,
        error_meta=error_meta,
    )
    return artifacts.model_dump(mode="json")
