from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.presentation import Presentation
from app.schemas.slide_generation_v2 import SlideGenerationArtifacts
from app.services.asset_reader_service import get_asset_parsed_document
from app.services.asset_service import require_user_asset
from app.services.llm_service import describe_visual_asset
from app.services.retrieval_service import search_asset_chunks
from app.services.slide_analysis_service import build_asset_slide_analysis_pack
from app.services.slide_html_authoring_service import build_slide_validation_result
from app.services.slide_html_authoring_service import render_slide_pages_batch
from app.services.slide_html_authoring_service import render_slide_page
from app.services.slide_html_authoring_service import render_slide_pages
from app.services.slide_processing_recovery_service import recover_stale_slides_processing
from app.services.slide_planning_service import _attach_page_budget
from app.services.slide_planning_service import _validate_presentation_plan
from app.services.slide_planning_service import build_plan_fallback
from app.services.slide_planning_service import build_presentation_plan
from app.services.slide_runtime_bundle_service import build_runtime_bundle
from app.services.slide_runtime_bundle_service import is_runtime_bundle_playable
from app.services.slide_runtime_bundle_service import summarize_runtime_bundle
from app.services.slide_scene_service import build_scene_specs
from app.services.slide_visual_asset_service import build_visual_asset_cards


DEBUG_TARGETS = {"analysis", "plan", "scene", "html", "full"}
REBUILD_STAGES = {"full", "scene", "html", "runtime"}
ALLOWED_STAGE_DEBUG_TARGETS: dict[str, set[str]] = {
    "full": {"analysis", "plan", "scene", "html", "full"},
    "scene": {"scene", "html", "full"},
    "html": {"html", "full"},
    "runtime": {"full"},
}


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


def enqueue_asset_slides_runtime_bundle_rebuild(
    db: Session,
    *,
    asset_id: str,
    user_id: str,
    from_stage: str,
    page_numbers: list[int] | None,
    failed_only: bool,
    reuse_analysis_pack: bool,
    reuse_presentation_plan: bool,
    debug_target: str,
) -> tuple[Asset, Presentation]:
    normalized_debug_target = _normalize_debug_target(debug_target)
    normalized_from_stage = _normalize_from_stage(from_stage)
    normalized_page_numbers = _normalize_page_numbers(page_numbers)
    _validate_stage_debug_target(normalized_from_stage, normalized_debug_target)
    if normalized_from_stage in {"full", "runtime"} and normalized_page_numbers:
        raise ValueError(
            f"page_numbers is only supported for from_stage=scene|html, got {normalized_from_stage}"
        )

    asset = require_user_asset(db, asset_id, user_id)
    presentation = _get_or_create_presentation(db, asset_id)
    recover_stale_slides_processing(db, asset=asset, presentation=presentation)

    if asset.slides_status == "processing" and presentation.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前资产演示内容正在生成中。",
        )

    presentation.status = "processing"
    asset.slides_status = "processing"
    presentation.active_run_token = None
    presentation.error_meta = {
        **(_coerce_persisted_dict(getattr(presentation, "error_meta", None))),
        "rebuild_meta": {
            "from_stage": normalized_from_stage,
            "requested_page_numbers": normalized_page_numbers,
            "effective_page_numbers": [],
            "failed_only": failed_only,
            "reused_layers": [],
            "rebuilt_layers": [],
        },
        "enqueue_meta": {
            "reuse_analysis_pack": reuse_analysis_pack,
            "reuse_presentation_plan": reuse_presentation_plan,
            "debug_target": normalized_debug_target,
        },
    }
    db.commit()
    db.refresh(asset)
    db.refresh(presentation)
    return asset, presentation



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
    asset = _require_asset(db, asset_id)
    parsed_document = get_asset_parsed_document(db, asset_id, asset.user_id)
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



def _coerce_persisted_dict(value: Any) -> dict[str, Any]:
    return _to_json_safe(value) if isinstance(value, dict) else {}



def _coerce_persisted_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_to_json_safe(item) for item in value if isinstance(item, dict)]



def _normalize_debug_target(debug_target: str) -> str:
    normalized_debug_target = (
        debug_target.strip().lower() if isinstance(debug_target, str) else "full"
    )
    if normalized_debug_target not in DEBUG_TARGETS:
        raise ValueError(f"unsupported debug target: {debug_target}")
    return normalized_debug_target



def _normalize_from_stage(from_stage: str) -> str:
    normalized_from_stage = (
        from_stage.strip().lower() if isinstance(from_stage, str) else "full"
    )
    if normalized_from_stage not in REBUILD_STAGES:
        raise ValueError(f"unsupported rebuild stage: {from_stage}")
    return normalized_from_stage



def _normalize_page_numbers(page_numbers: list[int] | None) -> list[int]:
    if page_numbers is None:
        return []
    normalized: list[int] = []
    seen: set[int] = set()
    for page_number in page_numbers:
        if not isinstance(page_number, int) or page_number <= 0:
            raise ValueError("page_numbers must contain positive integers")
        if page_number in seen:
            continue
        seen.add(page_number)
        normalized.append(page_number)
    return normalized



def _validate_stage_debug_target(from_stage: str, debug_target: str) -> None:
    allowed_targets = ALLOWED_STAGE_DEBUG_TARGETS[from_stage]
    if debug_target not in allowed_targets:
        raise ValueError(
            f"debug_target={debug_target} is not supported for from_stage={from_stage}"
        )



def _scene_fallback_from_plan(page: dict[str, Any], *, reason: str = "") -> dict[str, object]:
    narrative_goal = (
        str(page.get("narrative_goal", "Paper Overview")).strip() or "Paper Overview"
    )
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
        "_debug": {
            "scene_source": "fallback",
            "reason": reason,
            "is_empty_scene": True,
            "content_blocks_count": 0,
            "citations_count": 0,
            "asset_bindings_count": len(asset_bindings),
        },
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
    plan = _attach_page_budget(plan)
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
        "reason": "",
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
    return build_runtime_bundle([])



def _derive_final_slides_status(
    debug_target: str,
    runtime_bundle: dict[str, Any],
) -> str:
    if debug_target in {"analysis", "plan", "scene"}:
        return "processing"
    runtime_summary = summarize_runtime_bundle(runtime_bundle)
    if runtime_summary["playable_page_count"] > 0:
        return "ready"
    return "failed"



def _derive_deck_style_guide(presentation_plan: dict[str, Any]) -> dict[str, Any]:
    style_guide = presentation_plan.get("deck_style_guide")
    if isinstance(style_guide, dict):
        return style_guide
    return {
        "theme_name": "paper-academic",
        "language": "zh-CN",
        "layout_grammar": "headline-plus-evidence",
        "citation_style": "inline-footnote",
        "animation_pacing": "restrained",
    }



def _build_scene_specs_with_page_isolation(
    active_scene_builder: Callable[..., list[dict[str, object]]],
    presentation_plan: dict[str, Any],
    *,
    analysis_pack: dict[str, Any],
    visual_asset_catalog: list[dict[str, object]],
    deck_style_guide: dict[str, Any],
) -> list[dict[str, Any]]:
    pages = (
        presentation_plan.get("pages", [])
        if isinstance(presentation_plan.get("pages"), list)
        else []
    )
    scene_specs: list[dict[str, Any]] = []
    for page in pages:
        single_page_plan = {
            **presentation_plan,
            "page_count": 1,
            "pages": [page],
            "deck_style_guide": deck_style_guide,
        }
        try:
            raw_scene_specs = _to_json_safe(
                active_scene_builder(
                    single_page_plan,
                    analysis_pack=analysis_pack,
                    visual_asset_catalog=_to_json_safe(visual_asset_catalog),
                    deck_style_guide=deck_style_guide,
                    parallelism=settings.slides_scene_parallelism,
                )
            )
            if isinstance(raw_scene_specs, list) and raw_scene_specs:
                matched_scene_spec = next(
                    (
                        scene_spec
                        for scene_spec in raw_scene_specs
                        if isinstance(scene_spec, dict)
                        and scene_spec.get("page_id") == page.get("page_id")
                    ),
                    raw_scene_specs[0],
                )
                scene_specs.append(matched_scene_spec)
                continue
        except Exception as exc:
            scene_specs.append(_to_json_safe(_scene_fallback_from_plan(page, reason=str(exc))))
    return scene_specs



def _page_id_order(presentation_plan: dict[str, Any]) -> list[str]:
    pages = presentation_plan.get("pages") if isinstance(presentation_plan, dict) else []
    if not isinstance(pages, list):
        return []
    page_ids: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_id = page.get("page_id")
        if isinstance(page_id, str) and page_id.strip():
            page_ids.append(page_id)
    return page_ids



def _page_ids_from_numbers(
    presentation_plan: dict[str, Any],
    page_numbers: list[int],
) -> list[str]:
    if not page_numbers:
        return []
    page_ids = _page_id_order(presentation_plan)
    if not page_ids:
        raise ValueError("page-scoped rebuild requires an existing presentation plan")
    resolved_page_ids: list[str] = []
    for page_number in page_numbers:
        if page_number > len(page_ids):
            raise ValueError(f"page_numbers contains out-of-range page: {page_number}")
        resolved_page_ids.append(page_ids[page_number - 1])
    return resolved_page_ids



def _filter_plan_by_page_ids(
    presentation_plan: dict[str, Any],
    page_ids: set[str],
) -> dict[str, Any]:
    if not page_ids:
        return presentation_plan
    pages = presentation_plan.get("pages") if isinstance(presentation_plan, dict) else []
    filtered_pages = [
        page
        for page in pages
        if isinstance(page, dict) and page.get("page_id") in page_ids
    ]
    return {
        **presentation_plan,
        "page_count": len(filtered_pages),
        "pages": filtered_pages,
    }



def _filter_items_by_page_ids(
    items: list[dict[str, Any]],
    page_ids: set[str],
) -> list[dict[str, Any]]:
    if not page_ids:
        return items
    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("page_id") in page_ids
    ]



def _merge_page_scoped_items(
    existing_items: list[dict[str, Any]],
    updated_items: list[dict[str, Any]],
    ordered_page_ids: list[str],
) -> list[dict[str, Any]]:
    existing_by_page_id = {
        item["page_id"]: item
        for item in existing_items
        if isinstance(item, dict) and isinstance(item.get("page_id"), str)
    }
    updated_by_page_id = {
        item["page_id"]: item
        for item in updated_items
        if isinstance(item, dict) and isinstance(item.get("page_id"), str)
    }

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page_id in ordered_page_ids:
        if page_id in updated_by_page_id:
            merged.append(updated_by_page_id[page_id])
            seen.add(page_id)
            continue
        if page_id in existing_by_page_id:
            merged.append(existing_by_page_id[page_id])
            seen.add(page_id)

    for item in updated_items:
        page_id = item.get("page_id")
        if isinstance(page_id, str) and page_id not in seen:
            merged.append(item)
            seen.add(page_id)

    for item in existing_items:
        page_id = item.get("page_id")
        if isinstance(page_id, str) and page_id not in seen:
            merged.append(item)
            seen.add(page_id)

    return merged



def repair_rendered_slide_pages(
    rendered_pages: list[dict[str, Any]],
    *,
    rewrite_page_html: Callable[..., dict[str, Any]],
    max_total_extra_pages: int,
) -> list[dict[str, Any]]:
    repaired_pages: list[dict[str, Any]] = []
    extra_pages_used = 0

    for page in rendered_pages:
        render_meta = page.get("render_meta") if isinstance(page.get("render_meta"), dict) else {}
        validation = (
            render_meta.get("validation") if isinstance(render_meta.get("validation"), dict) else {}
        )
        repair_hints = (
            render_meta.get("repair_hints") if isinstance(render_meta.get("repair_hints"), dict) else {}
        )
        blocking = bool(validation.get("blocking"))
        residue = (
            repair_hints.get("overflow_residue")
            if isinstance(repair_hints.get("overflow_residue"), list)
            else []
        )

        if not blocking:
            repaired_pages.append(
                {
                    **page,
                    "render_meta": {
                        **render_meta,
                        "repair_state": "trimmed_ok"
                        if repair_hints.get("status") == "trimmed"
                        else "clean_ok",
                    },
                }
            )
            continue

        rewritten = _to_json_safe(
            rewrite_page_html(
                page,
                failure_reason=validation.get("reason"),
                overflow_residue=residue,
            )
        )
        rewritten_meta = (
            rewritten.get("render_meta") if isinstance(rewritten.get("render_meta"), dict) else {}
        )
        rewritten_validation = (
            rewritten_meta.get("validation")
            if isinstance(rewritten_meta.get("validation"), dict)
            else {}
        )
        if not bool(rewritten_validation.get("blocking")):
            repaired_pages.append(
                {
                    **rewritten,
                    "render_meta": {
                        **rewritten_meta,
                        "repair_state": "rewritten_ok",
                    },
                }
            )
            continue

        repaired_pages.append(
            {
                **page,
                "render_meta": {
                    **render_meta,
                    "repair_state": "failed_after_rewrite",
                },
            }
        )
        if residue and extra_pages_used < max_total_extra_pages:
            extra_pages_used += 1
            repaired_pages.append(
                {
                    "page_id": f"{page['page_id']}-cont-{extra_pages_used}",
                    "page_number": int(page.get("page_number", len(repaired_pages))) + 1,
                    "html": "<section>Continuation</section>",
                    "css": str(page.get("css") or ""),
                    "asset_refs": page.get("asset_refs", []),
                    "render_meta": {
                        "repair_state": "split_continuation",
                        "continuation_from": page["page_id"],
                        "carried_residue_count": len(residue),
                        "validation": {
                            "status": "passed",
                            "blocking": False,
                            "reason": None,
                        },
                    },
                }
            )

    return repaired_pages



def enrich_rendered_slide_pages_for_runtime(
    rendered_pages: list[dict[str, Any]],
    *,
    canvas_width: int,
    canvas_height: int,
    validation_enabled: bool,
    validate_page_html: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    for index, page in enumerate(rendered_pages, start=1):
        render_meta = page.setdefault("render_meta", {})
        if not isinstance(render_meta, dict):
            render_meta = {}
            page["render_meta"] = render_meta
        render_meta["canvas"] = {
            "width": canvas_width,
            "height": canvas_height,
        }

        if validation_enabled:
            validation = _to_json_safe(
                validate_page_html(
                    page_number=index,
                    html=str(page.get("html") or ""),
                    css=str(page.get("css") or ""),
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                )
            )
        else:
            validation = {
                "status": "skipped",
                "blocking": False,
                "reason": "validation_disabled",
            }

        render_meta["validation"] = validation
        render_meta["runtime_gate_status"] = (
            "failed" if bool(validation.get("blocking")) else "ready"
        )

    return rendered_pages



def finalize_rendered_slide_pages_for_runtime(
    rendered_pages: list[dict[str, Any]],
    *,
    canvas_width: int,
    canvas_height: int,
    validation_enabled: bool,
    validate_page_html: Callable[..., dict[str, Any]],
    runtime_bundle_builder: Callable[[list[dict[str, Any]]], dict[str, object]],
) -> dict[str, Any]:
    enriched_pages = enrich_rendered_slide_pages_for_runtime(
        rendered_pages,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        validation_enabled=validation_enabled,
        validate_page_html=validate_page_html,
    )
    bundle = _to_json_safe(runtime_bundle_builder(enriched_pages))
    bundle_summary = summarize_runtime_bundle(bundle)
    return {
        **bundle,
        "page_count": bundle_summary["page_count"],
        "playable_page_count": bundle_summary["playable_page_count"],
        "failed_page_numbers": bundle_summary["failed_page_numbers"],
        "validation_summary": bundle_summary["validation_summary"],
    }



def _runtime_bundle_has_page_level_validation(bundle: dict[str, Any]) -> bool:
    pages = bundle.get("pages") if isinstance(bundle, dict) else []
    if not isinstance(pages, list):
        return False
    for page in pages:
        if not isinstance(page, dict):
            continue
        render_meta = page.get("render_meta")
        if not isinstance(render_meta, dict):
            continue
        validation = render_meta.get("validation")
        if isinstance(validation, dict) and validation:
            return True
        gate_status = render_meta.get("runtime_gate_status")
        if isinstance(gate_status, str) and gate_status.strip():
            return True
    return False



def _resolve_failed_page_numbers_for_rebuild(runtime_bundle: dict[str, Any]) -> list[int]:
    summary_failed_page_numbers = summarize_runtime_bundle(runtime_bundle)["failed_page_numbers"]
    if summary_failed_page_numbers:
        return summary_failed_page_numbers
    if _runtime_bundle_has_page_level_validation(runtime_bundle):
        return summary_failed_page_numbers
    explicit_failed_page_numbers = runtime_bundle.get("failed_page_numbers") if isinstance(runtime_bundle, dict) else []
    if not isinstance(explicit_failed_page_numbers, list):
        return []
    return [value for value in explicit_failed_page_numbers if isinstance(value, int) and value > 0]



def _resolve_effective_page_numbers(
    requested_page_numbers: list[int],
    *,
    failed_only: bool,
    runtime_bundle: dict[str, Any],
) -> list[int]:
    if requested_page_numbers:
        return requested_page_numbers
    if not failed_only:
        return []
    return _resolve_failed_page_numbers_for_rebuild(runtime_bundle)



def _validate_failed_only_threshold(
    runtime_bundle: dict[str, Any],
    *,
    failed_page_numbers: list[int],
) -> None:
    summary = summarize_runtime_bundle(runtime_bundle)
    page_count = max(1, int(summary.get("page_count") or 0))
    failed_ratio = len(failed_page_numbers) / page_count
    if failed_ratio > settings.slides_html_failed_only_max_ratio:
        raise ValueError("failed_only rebuild exceeds threshold; rerun full generation")



def _append_plan_reused_meta(
    error_meta: dict[str, Any],
    presentation_plan: dict[str, Any],
) -> None:
    pages = presentation_plan.get("pages") if isinstance(presentation_plan, dict) else []
    error_meta["plan_generation"].append(
        {
            "status": "reused",
            "reason": "",
            "fallback_used": False,
            "planner_status": "reused",
            "planner_error": "",
            "page_count": len(pages) if isinstance(pages, list) else 0,
            "plan_source": "persisted",
            "internal_fallback_used": False,
            "internal_error": "",
            "raw_page_count": len(pages) if isinstance(pages, list) else 0,
            "validated_page_count": len(pages) if isinstance(pages, list) else 0,
        }
    )



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
    batch_html_renderer: Callable[..., dict[str, object]] = render_slide_pages_batch,
    llm_enabled: bool | None = None,
    llm_plan_builder: Callable[[dict[str, Any], list[dict[str, object]]], dict[str, object]] | None = None,
    llm_scene_builder: Callable[[dict[str, object], dict[str, Any], list[dict[str, object]]], list[dict[str, object]]] | None = None,
    llm_html_renderer: Callable[[dict[str, object]], dict[str, object]] | None = None,
    runtime_bundle_builder: Callable[..., dict[str, object]] = build_runtime_bundle,
    debug_target: str = "full",
    from_stage: str = "full",
    page_numbers: list[int] | None = None,
    failed_only: bool = False,
    reuse_analysis_pack: bool = True,
    reuse_presentation_plan: bool = True,
) -> dict[str, Any]:
    normalized_debug_target = _normalize_debug_target(debug_target)
    normalized_from_stage = _normalize_from_stage(from_stage)
    normalized_page_numbers = _normalize_page_numbers(page_numbers)
    _validate_stage_debug_target(normalized_from_stage, normalized_debug_target)
    if normalized_from_stage in {"full", "runtime"} and normalized_page_numbers:
        raise ValueError(
            f"page_numbers is only supported for from_stage=scene|html, got {normalized_from_stage}"
        )

    asset = _require_asset(db, asset_id)
    presentation = _get_or_create_presentation(db, asset_id)

    persisted_analysis_pack = _coerce_persisted_dict(getattr(presentation, "analysis_pack", None))
    persisted_visual_asset_catalog = _coerce_persisted_list(
        getattr(presentation, "visual_asset_catalog", None)
    )
    persisted_presentation_plan = _coerce_persisted_dict(
        getattr(presentation, "presentation_plan", None)
    )
    persisted_scene_specs = _coerce_persisted_list(getattr(presentation, "scene_specs", None))
    persisted_rendered_slide_pages = _coerce_persisted_list(
        getattr(presentation, "rendered_slide_pages", None)
    )
    persisted_runtime_bundle = _coerce_persisted_dict(
        getattr(presentation, "runtime_bundle", None)
    )

    persisted_deck_meta = _coerce_persisted_dict(
        persisted_runtime_bundle.get("deck_meta") if isinstance(persisted_runtime_bundle, dict) else {}
    )

    effective_page_numbers = _resolve_effective_page_numbers(
        normalized_page_numbers,
        failed_only=failed_only,
        runtime_bundle=persisted_runtime_bundle,
    )

    if failed_only and not normalized_page_numbers and effective_page_numbers:
        _validate_failed_only_threshold(
            persisted_runtime_bundle,
            failed_page_numbers=effective_page_numbers,
        )

    reused_layers: list[str] = []
    rebuilt_layers: list[str] = []
    rebuild_meta: dict[str, Any] = {
        "from_stage": normalized_from_stage,
        "requested_page_numbers": normalized_page_numbers,
        "effective_page_numbers": effective_page_numbers,
        "failed_only": failed_only,
        "reused_layers": reused_layers,
        "rebuilt_layers": rebuilt_layers,
    }
    error_meta: dict[str, Any] = {
        "debug_target": normalized_debug_target,
        "rebuild_meta": rebuild_meta,
        "plan_generation": [],
        "scene_generation": [],
        "html_generation": [],
    }

    presentation.status = "processing"
    asset.slides_status = "processing"
    db.commit()
    db.refresh(asset)

    should_use_llm = settings.slides_llm_enabled if llm_enabled is None else llm_enabled
    active_plan_builder = plan_builder
    active_scene_builder = scene_builder
    active_html_renderer = html_renderer

    analysis_pack: dict[str, Any] = {}
    visual_asset_catalog: list[dict[str, Any]] = []
    presentation_plan: dict[str, Any] = {}
    scene_specs: list[dict[str, Any]] = []
    rendered_slide_pages: list[dict[str, Any]] = []
    runtime_bundle = _to_json_safe(_build_empty_runtime_bundle())
    deck_style_guide: dict[str, Any] = {}
    parsed_payload_value = parsed_payload

    def ensure_parsed_payload() -> dict[str, Any]:
        nonlocal parsed_payload_value
        if parsed_payload_value is None:
            parsed_payload_value = parsed_payload_loader(db, asset_id)
        return parsed_payload_value

    def ensure_analysis_and_visuals(*, force_rebuild: bool) -> None:
        nonlocal analysis_pack, visual_asset_catalog
        if force_rebuild or not analysis_pack:
            payload = ensure_parsed_payload()
            visual_assets = _collect_visual_assets(payload)
            analysis_result = analysis_builder(
                db,
                asset_id=asset_id,
                search_func=search_func,
            )
            analysis_pack = _to_json_safe(_coerce_analysis_pack(analysis_result))
            visual_asset_catalog = _to_json_safe(visual_asset_builder(visual_assets))
            rebuilt_layers.extend(
                [
                    layer
                    for layer in ["analysis_pack", "visual_asset_catalog"]
                    if layer not in rebuilt_layers
                ]
            )
            return
        if not visual_asset_catalog:
            payload = ensure_parsed_payload()
            visual_assets = _collect_visual_assets(payload)
            visual_asset_catalog = _to_json_safe(visual_asset_builder(visual_assets))
            if "visual_asset_catalog" not in rebuilt_layers:
                rebuilt_layers.append("visual_asset_catalog")

    def build_or_reuse_plan(*, force_rebuild: bool) -> None:
        nonlocal presentation_plan, deck_style_guide
        if not force_rebuild and persisted_presentation_plan:
            presentation_plan = _to_json_safe(persisted_presentation_plan)
            deck_style_guide = _derive_deck_style_guide(presentation_plan)
            presentation_plan["deck_style_guide"] = deck_style_guide
            if "presentation_plan" not in reused_layers:
                reused_layers.append("presentation_plan")
            _append_plan_reused_meta(error_meta, presentation_plan)
            return

        try:
            raw_plan = _build_validated_plan(
                active_plan_builder,
                analysis_pack,
                _to_json_safe(visual_asset_catalog),
            )
            plan_debug = _extract_plan_debug(raw_plan)
            presentation_plan = _strip_plan_debug(raw_plan)
            deck_style_guide = _derive_deck_style_guide(presentation_plan)
            presentation_plan["deck_style_guide"] = deck_style_guide
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
                    "internal_fallback_used": bool(
                        plan_debug.get("internal_fallback_used", False)
                    ),
                    "internal_error": str(plan_debug.get("internal_error", "")),
                    "raw_page_count": int(plan_debug.get("raw_page_count", len(pages)) or 0),
                    "validated_page_count": int(
                        plan_debug.get("validated_page_count", len(pages)) or 0
                    ),
                }
            )
        except Exception as exc:
            presentation_plan = _to_json_safe(
                _plan_fallback_from_inputs(
                    analysis_pack,
                    _to_json_safe(visual_asset_catalog),
                )
            )
            deck_style_guide = _derive_deck_style_guide(presentation_plan)
            presentation_plan["deck_style_guide"] = deck_style_guide
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
                    "validated_page_count": int(
                        presentation_plan.get("page_count", 1) or 0
                    ),
                }
            )
        if "presentation_plan" not in rebuilt_layers:
            rebuilt_layers.append("presentation_plan")

    if should_use_llm:
        if llm_plan_builder is not None:
            active_plan_builder = llm_plan_builder
        if llm_scene_builder is not None:
            active_scene_builder = lambda current_plan, **_kwargs: llm_scene_builder(
                current_plan,
                analysis_pack,
                visual_asset_catalog,
            )
        if llm_html_renderer is not None:
            active_html_renderer = llm_html_renderer

    if normalized_from_stage == "full":
        ensure_analysis_and_visuals(force_rebuild=True)
        if normalized_debug_target != "analysis":
            build_or_reuse_plan(force_rebuild=True)
    elif normalized_from_stage == "scene":
        if reuse_analysis_pack and persisted_analysis_pack:
            analysis_pack = _to_json_safe(persisted_analysis_pack)
            if "analysis_pack" not in reused_layers:
                reused_layers.append("analysis_pack")
            visual_asset_catalog = _to_json_safe(persisted_visual_asset_catalog)
            if persisted_visual_asset_catalog and "visual_asset_catalog" not in reused_layers:
                reused_layers.append("visual_asset_catalog")
            ensure_analysis_and_visuals(force_rebuild=False)
        else:
            ensure_analysis_and_visuals(force_rebuild=True)
        build_or_reuse_plan(force_rebuild=not (reuse_presentation_plan and persisted_presentation_plan))
    else:
        analysis_pack = _to_json_safe(persisted_analysis_pack)
        visual_asset_catalog = _to_json_safe(persisted_visual_asset_catalog)
        presentation_plan = _to_json_safe(persisted_presentation_plan)
        if persisted_analysis_pack and "analysis_pack" not in reused_layers:
            reused_layers.append("analysis_pack")
        if persisted_visual_asset_catalog and "visual_asset_catalog" not in reused_layers:
            reused_layers.append("visual_asset_catalog")
        if persisted_presentation_plan:
            deck_style_guide = _derive_deck_style_guide(presentation_plan)
            presentation_plan["deck_style_guide"] = deck_style_guide
            if "presentation_plan" not in reused_layers:
                reused_layers.append("presentation_plan")

    ordered_page_ids = _page_id_order(presentation_plan)
    target_page_ids = set(_page_ids_from_numbers(presentation_plan, effective_page_numbers))
    should_rebuild_subset = bool(target_page_ids)
    should_skip_targeted_rebuild = failed_only and not target_page_ids and bool(normalized_page_numbers or persisted_runtime_bundle)
    skip_failed_only_rebuild = (
        should_skip_targeted_rebuild and normalized_from_stage in {"scene", "html"}
    )

    if normalized_from_stage in {"scene", "html"} and failed_only and not effective_page_numbers:
        scene_specs = _to_json_safe(persisted_scene_specs)
        rendered_slide_pages = _to_json_safe(persisted_rendered_slide_pages)
        runtime_bundle = (
            _to_json_safe(persisted_runtime_bundle)
            if persisted_runtime_bundle
            else runtime_bundle
        )
        if persisted_scene_specs and "scene_specs" not in reused_layers:
            reused_layers.append("scene_specs")
        if persisted_rendered_slide_pages and "rendered_slide_pages" not in reused_layers:
            reused_layers.append("rendered_slide_pages")
        if persisted_runtime_bundle and "runtime_bundle" not in reused_layers:
            reused_layers.append("runtime_bundle")

    if normalized_debug_target not in {"analysis", "plan"} and not skip_failed_only_rebuild:
        if normalized_from_stage in {"full", "scene"}:
            scene_plan = (
                _filter_plan_by_page_ids(presentation_plan, target_page_ids)
                if should_rebuild_subset
                else presentation_plan
            )
            try:
                raw_scene_specs = _build_scene_specs_with_page_isolation(
                    active_scene_builder,
                    scene_plan,
                    analysis_pack=analysis_pack,
                    visual_asset_catalog=_to_json_safe(visual_asset_catalog),
                    deck_style_guide=deck_style_guide,
                )
                new_scene_specs = [
                    _strip_scene_debug(scene_spec) for scene_spec in raw_scene_specs
                ]
                for scene_spec, raw_scene_spec in zip(
                    new_scene_specs,
                    raw_scene_specs,
                    strict=False,
                ):
                    scene_debug = _extract_scene_debug(raw_scene_spec)
                    error_meta["scene_generation"].append(
                        {
                            "page_id": scene_spec.get("page_id", "unknown"),
                            "status": "fallback"
                            if scene_debug.get("scene_source") == "fallback"
                            else "success",
                            "reason": str(scene_debug.get("reason", "")),
                            "scene_source": scene_debug.get("scene_source", "generated"),
                            "is_empty_scene": bool(
                                scene_debug.get("is_empty_scene", False)
                            ),
                            "content_blocks_count": int(
                                scene_debug.get("content_blocks_count", 0) or 0
                            ),
                            "citations_count": int(
                                scene_debug.get("citations_count", 0) or 0
                            ),
                            "asset_bindings_count": int(
                                scene_debug.get("asset_bindings_count", 0) or 0
                            ),
                        }
                    )
            except Exception as exc:
                fallback_pages = (
                    scene_plan.get("pages", [])
                    if isinstance(scene_plan.get("pages"), list)
                    else []
                )
                new_scene_specs = [_scene_fallback_from_plan(page) for page in fallback_pages]
                for page in fallback_pages:
                    error_meta["scene_generation"].append(
                        {
                            "page_id": page.get("page_id", "unknown"),
                            "status": "fallback",
                            "reason": str(exc),
                        }
                    )

            if should_rebuild_subset:
                scene_specs = _merge_page_scoped_items(
                    persisted_scene_specs,
                    [_to_json_safe(item) for item in new_scene_specs],
                    ordered_page_ids,
                )
            else:
                scene_specs = [_to_json_safe(item) for item in new_scene_specs]
            if "scene_specs" not in rebuilt_layers:
                rebuilt_layers.append("scene_specs")
        elif normalized_from_stage in {"html", "runtime"}:
            scene_specs = _to_json_safe(persisted_scene_specs)
            if persisted_scene_specs and "scene_specs" not in reused_layers:
                reused_layers.append("scene_specs")

    if normalized_debug_target not in {"analysis", "plan", "scene"} and not skip_failed_only_rebuild:
        batch_deck_meta: dict[str, Any] = {}
        batch_generation_meta: dict[str, Any] = {}
        page_deck_style_guide = {
            **deck_style_guide,
            "deck_meta": persisted_deck_meta,
        } if persisted_deck_meta else deck_style_guide
        if normalized_from_stage == "full":
            html_bundle = batch_html_renderer(
                scene_specs,
                deck_style_guide=deck_style_guide,
                deck_digest={
                    "page_roles": [
                        str(page.get("scene_role", ""))
                        for page in presentation_plan.get("pages", [])
                        if isinstance(page, dict)
                    ],
                    "page_count": len(scene_specs),
                },
                max_batch_pages=settings.slides_html_batch_max_pages,
                chunk_size=settings.slides_html_batch_chunk_size,
                page_html_writer=active_html_renderer,
            )
            rendered_slide_pages = [
                _to_json_safe(page)
                for page in html_bundle.get("pages", [])
                if isinstance(page, dict)
            ]
            generation_mode = (
                "batch_chunked"
                if len(scene_specs) > settings.slides_html_batch_max_pages
                else "batch"
            )
            chunk_size = max(1, int(settings.slides_html_batch_chunk_size or 1))
            batch_count = (
                1
                if len(scene_specs) <= settings.slides_html_batch_max_pages
                else max(1, (len(scene_specs) + chunk_size - 1) // chunk_size)
            )
            bundled_html_meta = html_bundle.get("html_meta") if isinstance(html_bundle.get("html_meta"), list) else []
            if bundled_html_meta:
                error_meta["html_generation"] = [_to_json_safe(item) for item in bundled_html_meta]
            else:
                error_meta["html_generation"] = [
                    {
                        "status": "success",
                        "reason": "",
                        "mode": generation_mode,
                        "page_count": len(rendered_slide_pages),
                    }
                ]
            batch_deck_meta = _to_json_safe(
                html_bundle.get("deck_meta")
                if isinstance(html_bundle.get("deck_meta"), dict)
                else {}
            )
            batch_generation_meta = {
                "html_generation_mode": generation_mode,
                "html_batch_count": batch_count,
                "html_batch_page_count": len(rendered_slide_pages),
            }
            if "rendered_slide_pages" not in rebuilt_layers:
                rebuilt_layers.append("rendered_slide_pages")
        elif normalized_from_stage == "scene":
            scene_specs_to_render = (
                _filter_items_by_page_ids(scene_specs, target_page_ids)
                if should_rebuild_subset
                else scene_specs
            )
            rendered_subset, html_meta = render_slide_pages(
                scene_specs_to_render,
                html_writer=active_html_renderer,
                parallelism=settings.slides_html_parallelism,
                deck_style_guide=page_deck_style_guide,
            )
            rendered_subset = [_to_json_safe(page) for page in rendered_subset]
            error_meta["html_generation"] = [_to_json_safe(item) for item in html_meta]
            if should_rebuild_subset:
                rendered_slide_pages = _merge_page_scoped_items(
                    persisted_rendered_slide_pages,
                    rendered_subset,
                    ordered_page_ids,
                )
            else:
                rendered_slide_pages = rendered_subset
            if "rendered_slide_pages" not in rebuilt_layers:
                rebuilt_layers.append("rendered_slide_pages")
        elif normalized_from_stage == "html":
            scene_specs = _to_json_safe(persisted_scene_specs)
            if not scene_specs:
                raise ValueError(
                    "from_stage=html requires persisted scene_specs before rebuilding html"
                )
            if "scene_specs" not in reused_layers:
                reused_layers.append("scene_specs")
            scene_specs_to_render = (
                _filter_items_by_page_ids(scene_specs, target_page_ids)
                if should_rebuild_subset
                else scene_specs
            )
            rendered_subset, html_meta = render_slide_pages(
                scene_specs_to_render,
                html_writer=active_html_renderer,
                parallelism=settings.slides_html_parallelism,
                deck_style_guide=page_deck_style_guide,
            )
            rendered_subset = [_to_json_safe(page) for page in rendered_subset]
            error_meta["html_generation"] = [_to_json_safe(item) for item in html_meta]
            if should_rebuild_subset:
                rendered_slide_pages = _merge_page_scoped_items(
                    persisted_rendered_slide_pages,
                    rendered_subset,
                    ordered_page_ids,
                )
            else:
                rendered_slide_pages = rendered_subset
            if "rendered_slide_pages" not in rebuilt_layers:
                rebuilt_layers.append("rendered_slide_pages")
        elif normalized_from_stage == "runtime":
            rendered_slide_pages = _to_json_safe(persisted_rendered_slide_pages)
            if persisted_rendered_slide_pages and "rendered_slide_pages" not in reused_layers:
                reused_layers.append("rendered_slide_pages")

        rendered_slide_pages = enrich_rendered_slide_pages_for_runtime(
            rendered_slide_pages,
            canvas_width=settings.slides_html_canvas_width,
            canvas_height=settings.slides_html_canvas_height,
            validation_enabled=settings.slides_html_validation_enabled,
            validate_page_html=lambda **kwargs: build_slide_validation_result(
                enabled=settings.slides_html_validation_enabled,
                page_number=int(kwargs.get("page_number") or 0),
                html=str(kwargs.get("html") or ""),
                css=str(kwargs.get("css") or ""),
                canvas_width=settings.slides_html_canvas_width,
                canvas_height=settings.slides_html_canvas_height,
                timeout_sec=settings.slides_html_validation_timeout_sec,
            ),
        )
        repaired_pages = repair_rendered_slide_pages(
            rendered_slide_pages,
            rewrite_page_html=lambda page, failure_reason, overflow_residue: {
                **page,
                "render_meta": {
                    **(
                        page.get("render_meta")
                        if isinstance(page.get("render_meta"), dict)
                        else {}
                    ),
                    "validation": {
                        **(
                            page.get("render_meta", {}).get("validation", {})
                            if isinstance(page.get("render_meta"), dict)
                            and isinstance(page.get("render_meta", {}).get("validation"), dict)
                            else {}
                        ),
                        "status": "failed",
                        "blocking": True,
                        "reason": str(failure_reason or "repair_rewrite_failed"),
                    },
                    "repair_hints": {
                        **(
                            page.get("render_meta", {}).get("repair_hints", {})
                            if isinstance(page.get("render_meta"), dict)
                            and isinstance(page.get("render_meta", {}).get("repair_hints"), dict)
                            else {}
                        ),
                        "overflow_residue": overflow_residue,
                    },
                },
            },
            max_total_extra_pages=3,
        )
        rendered_slide_pages = [_to_json_safe(page) for page in repaired_pages]
        runtime_bundle = finalize_rendered_slide_pages_for_runtime(
            rendered_slide_pages,
            canvas_width=settings.slides_html_canvas_width,
            canvas_height=settings.slides_html_canvas_height,
            validation_enabled=settings.slides_html_validation_enabled,
            validate_page_html=lambda **kwargs: build_slide_validation_result(
                enabled=settings.slides_html_validation_enabled,
                page_number=int(kwargs.get("page_number") or 0),
                html=str(kwargs.get("html") or ""),
                css=str(kwargs.get("css") or ""),
                canvas_width=settings.slides_html_canvas_width,
                canvas_height=settings.slides_html_canvas_height,
                timeout_sec=settings.slides_html_validation_timeout_sec,
            ),
            runtime_bundle_builder=runtime_bundle_builder,
        )
        if batch_deck_meta:
            runtime_bundle["deck_meta"] = batch_deck_meta
        if batch_generation_meta:
            runtime_bundle["generation_meta"] = batch_generation_meta
        if "runtime_bundle" not in rebuilt_layers:
            rebuilt_layers.append("runtime_bundle")

    final_slides_status = _derive_final_slides_status(normalized_debug_target, runtime_bundle)
    presentation.analysis_pack = analysis_pack
    presentation.visual_asset_catalog = _to_json_safe(visual_asset_catalog)
    presentation.presentation_plan = presentation_plan
    presentation.scene_specs = scene_specs
    presentation.rendered_slide_pages = rendered_slide_pages
    presentation.runtime_bundle = runtime_bundle
    presentation.status = final_slides_status
    presentation.error_meta = error_meta
    asset.slides_status = final_slides_status
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
