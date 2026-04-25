from __future__ import annotations

from collections.abc import Callable

from app.services.llm_service import generate_slides_presentation_plan


def _analysis_has_rich_coverage(analysis_pack: dict[str, object]) -> bool:
    coverage_keys = (
        "problem_statements",
        "method_components",
        "main_results",
        "ablations",
        "limitations",
    )
    covered = 0
    for key in coverage_keys:
        value = analysis_pack.get(key)
        if isinstance(value, list) and value:
            covered += 1
    return covered >= 4


def _default_page_budget(scene_role: str, visual_strategy: str) -> dict[str, object]:
    del scene_role
    visual_heavy = visual_strategy in {
        "text_plus_original_figure",
        "comparison_with_original_table",
    }
    return {
        "max_blocks": 2 if visual_heavy else 3,
        "layout_budget": {
            "visual_emphasis": "high" if visual_heavy else "medium",
            "safe_area_padding": 72,
        },
        "content_budget": {
            "title_max_chars": 28,
            "summary_max_chars": 72,
            "bullet_max_items": 4,
            "bullet_max_chars": 44,
            "evidence_max_chars": 90,
        },
        "priority_tiers": {
            "must_keep": ["title", "summary_line"],
            "trim_first": ["evidence", "secondary_bullets"],
            "split_candidates": ["overflow_bullets", "overflow_evidence"],
        },
        "overflow_strategy": {
            "mode": "trim_then_split",
            "trim_order": ["evidence", "secondary_bullets", "speaker_note_seed"],
            "split_threshold": "after_trim_if_still_over_budget",
        },
        "continuation_policy": {
            "enabled": True,
            "max_extra_pages": 3,
            "title_suffix": "（续）",
        },
    }


def _attach_page_budget(plan: dict[str, object]) -> dict[str, object]:
    pages = plan.get("pages")
    if not isinstance(pages, list):
        return plan

    enriched_pages: list[dict[str, object]] = []
    for page in pages:
        if not isinstance(page, dict):
            enriched_pages.append(page)
            continue
        enriched_pages.append(
            {
                **page,
                "page_budget": page.get("page_budget")
                if isinstance(page.get("page_budget"), dict)
                else _default_page_budget(
                    str(page.get("scene_role", "overview")),
                    str(page.get("visual_strategy", "text_only")),
                ),
            }
        )

    return {
        **plan,
        "pages": enriched_pages,
    }


def _validate_presentation_plan(
    plan: dict[str, object],
    analysis_pack: dict[str, object],
    visual_asset_catalog: list[dict[str, object]],
) -> None:
    if "page_count" not in plan or "pages" not in plan:
        raise ValueError("presentation plan missing required keys")
    pages = plan.get("pages")
    if not isinstance(pages, list):
        raise ValueError("presentation plan pages must be a list")
    if not pages:
        raise ValueError("presentation plan pages cannot be empty")
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("presentation plan pages must contain dict items")
        budget = page.get("page_budget")
        if not isinstance(budget, dict):
            raise ValueError("presentation plan page missing page_budget")
        if int(budget.get("max_blocks", 0) or 0) <= 0:
            raise ValueError("presentation plan page_budget.max_blocks must be positive")
    if _analysis_has_rich_coverage(analysis_pack) and visual_asset_catalog and len(pages) < 4:
        raise ValueError("presentation plan collapsed rich analysis into too few pages")


def _plan_page_count(plan: dict[str, object]) -> int:
    pages = plan.get("pages")
    if isinstance(pages, list):
        return len(pages)
    return 0


def _with_plan_debug(plan: dict[str, object], **debug: object) -> dict[str, object]:
    return {
        **plan,
        "_debug": debug,
    }


def _default_plan_writer(
    analysis_pack: dict[str, object],
    visual_asset_catalog: list[dict[str, object]],
) -> dict[str, object]:
    title = "Paper Overview"
    core_claims = analysis_pack.get("core_claims")
    if isinstance(core_claims, list) and core_claims:
        first_claim = core_claims[0]
        if isinstance(first_claim, str) and first_claim.strip():
            title = first_claim.strip()[:80]

    candidate_assets = []
    if visual_asset_catalog:
        first_asset_id = visual_asset_catalog[0].get("asset_id")
        if isinstance(first_asset_id, str) and first_asset_id.strip():
            candidate_assets.append(first_asset_id)

    return {
        "page_count": 1,
        "pages": [
            {
                "page_id": "page-1",
                "scene_role": "overview",
                "narrative_goal": title,
                "content_focus": "core_claims",
                "visual_strategy": "text_plus_original_figure"
                if candidate_assets
                else "text_only",
                "candidate_assets": candidate_assets,
                "animation_intent": "soft_intro",
            }
        ],
    }


def _first_non_empty_text(values: object, fallback: str) -> str:
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _pick_asset_ids(
    visual_asset_catalog: list[dict[str, object]],
    *,
    preferred_usage: str | None = None,
    limit: int = 1,
) -> list[str]:
    picked: list[str] = []
    for asset in visual_asset_catalog:
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            continue
        usage = str(asset.get("recommended_usage", "")).strip()
        if preferred_usage and usage != preferred_usage:
            continue
        picked.append(asset_id.strip())
        if len(picked) >= limit:
            return picked
    if preferred_usage is not None and not picked:
        return _pick_asset_ids(visual_asset_catalog, preferred_usage=None, limit=limit)
    return picked


def _build_rich_plan_fallback(
    analysis_pack: dict[str, object],
    visual_asset_catalog: list[dict[str, object]],
) -> dict[str, object]:
    pages = [
        {
            "page_id": "page-1",
            "scene_role": "problem",
            "narrative_goal": _first_non_empty_text(
                analysis_pack.get("problem_statements"),
                "研究问题与动机",
            )[:120],
            "content_focus": "problem_statements",
            "visual_strategy": "text_only",
            "candidate_assets": [],
            "animation_intent": "soft_intro",
        },
        {
            "page_id": "page-2",
            "scene_role": "method",
            "narrative_goal": _first_non_empty_text(
                analysis_pack.get("method_components"),
                "方法整体结构",
            )[:120],
            "content_focus": "method_components",
            "visual_strategy": "text_plus_original_figure" if visual_asset_catalog else "text_only",
            "candidate_assets": _pick_asset_ids(visual_asset_catalog, preferred_usage="method_overview"),
            "animation_intent": "stagger_reveal",
        },
        {
            "page_id": "page-3",
            "scene_role": "results",
            "narrative_goal": _first_non_empty_text(
                analysis_pack.get("main_results"),
                "核心实验结果",
            )[:120],
            "content_focus": "main_results",
            "visual_strategy": "comparison_with_original_table" if visual_asset_catalog else "comparison_text",
            "candidate_assets": _pick_asset_ids(visual_asset_catalog, preferred_usage="results_comparison"),
            "animation_intent": "focus_emphasis",
        },
        {
            "page_id": "page-4",
            "scene_role": "limitations",
            "narrative_goal": _first_non_empty_text(
                analysis_pack.get("limitations"),
                "局限性与后续方向",
            )[:120],
            "content_focus": "limitations",
            "visual_strategy": "text_only",
            "candidate_assets": [],
            "animation_intent": "soft_intro",
        },
    ]
    return {"page_count": len(pages), "pages": pages}


def build_plan_fallback(
    analysis_pack: dict[str, object],
    visual_asset_catalog: list[dict[str, object]],
) -> dict[str, object]:
    if _analysis_has_rich_coverage(analysis_pack):
        return _build_rich_plan_fallback(analysis_pack, visual_asset_catalog)
    return _default_plan_writer(analysis_pack, visual_asset_catalog)


def build_presentation_plan(
    analysis_pack: dict[str, object],
    visual_asset_catalog: list[dict[str, object]],
    *,
    plan_writer: Callable[[dict[str, object], list[dict[str, object]]], dict[str, object]] = _default_plan_writer,
) -> dict[str, object]:
    raw_page_count = 0
    try:
        if plan_writer is _default_plan_writer:
            plan = generate_slides_presentation_plan(analysis_pack, visual_asset_catalog)
        else:
            plan = plan_writer(analysis_pack, visual_asset_catalog)
        plan = _attach_page_budget(plan)
        raw_page_count = _plan_page_count(plan)
        _validate_presentation_plan(plan, analysis_pack, visual_asset_catalog)
        return _with_plan_debug(
            plan,
            plan_source="generated",
            internal_fallback_used=False,
            internal_error="",
            raw_page_count=raw_page_count,
            validated_page_count=_plan_page_count(plan),
        )
    except Exception as exc:
        fallback_plan = _attach_page_budget(build_plan_fallback(analysis_pack, visual_asset_catalog))
        _validate_presentation_plan(fallback_plan, analysis_pack, visual_asset_catalog)
        return _with_plan_debug(
            fallback_plan,
            plan_source="fallback",
            internal_fallback_used=True,
            internal_error=str(exc),
            raw_page_count=raw_page_count,
            validated_page_count=_plan_page_count(fallback_plan),
        )
