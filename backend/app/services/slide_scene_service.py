from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.llm_service import generate_slide_scene_spec


def _default_scene_writer(page: dict[str, object]) -> dict[str, object]:
    narrative_goal = str(page.get("narrative_goal", "Paper Overview")).strip() or "Paper Overview"
    candidate_assets = page.get("candidate_assets")
    asset_bindings = []
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
            "is_empty_scene": True,
            "content_blocks_count": 0,
            "citations_count": 0,
            "asset_bindings_count": len(asset_bindings),
        },
    }


def _annotate_scene_debug(scene: dict[str, object], *, scene_source: str) -> dict[str, object]:
    content_blocks = scene.get("content_blocks")
    citations = scene.get("citations")
    asset_bindings = scene.get("asset_bindings")
    content_blocks_count = len(content_blocks) if isinstance(content_blocks, list) else 0
    citations_count = len(citations) if isinstance(citations, list) else 0
    asset_bindings_count = len(asset_bindings) if isinstance(asset_bindings, list) else 0
    return {
        **scene,
        "_debug": {
            "scene_source": scene_source,
            "is_empty_scene": content_blocks_count == 0 and citations_count == 0,
            "content_blocks_count": content_blocks_count,
            "citations_count": citations_count,
            "asset_bindings_count": asset_bindings_count,
        },
    }


def build_scene_specs(
    presentation_plan: dict[str, object],
    *,
    analysis_pack: dict[str, Any] | None = None,
    visual_asset_catalog: list[dict[str, object]] | None = None,
    scene_writer: Callable[[dict[str, object]], dict[str, object]] = _default_scene_writer,
    scene_generator: Callable[[dict[str, object], dict[str, Any], list[dict[str, object]]], dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    pages = presentation_plan.get("pages", [])
    if not isinstance(pages, list):
        raise ValueError("presentation plan pages must be a list")
    effective_analysis_pack = analysis_pack or {}
    effective_visual_asset_catalog = visual_asset_catalog or []
    if scene_generator is not None:
        return [
            _annotate_scene_debug(
                scene_generator(page, effective_analysis_pack, effective_visual_asset_catalog),
                scene_source="generated",
            )
            for page in pages
        ]
    if scene_writer is _default_scene_writer:
        try:
            return [
                _annotate_scene_debug(
                    generate_slide_scene_spec(
                        page,
                        effective_analysis_pack,
                        effective_visual_asset_catalog,
                    ),
                    scene_source="generated",
                )
                for page in pages
            ]
        except Exception:
            return [scene_writer(page) for page in pages]
    return [_annotate_scene_debug(scene_writer(page), scene_source="generated") for page in pages]
