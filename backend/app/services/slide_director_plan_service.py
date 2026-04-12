from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.services.llm_service import LLMRequestError, generate_slides_director_hint
from app.services.slide_markdown_service import SlideMarkdownDraftPage, SlideMarkdownDraftResult


@dataclass
class SlideDirectorHint:
    slide_key: str
    layout_hint: str
    animation_type: str
    target_block_type: str
    visual_tone: str
    source: str


def _fallback_hint(page: SlideMarkdownDraftPage, index: int) -> SlideDirectorHint:
    if page.page_type == "comparison":
        return SlideDirectorHint(
            slide_key=page.slide_key,
            layout_hint="data-table",
            animation_type="compare_switch",
            target_block_type="comparison",
            visual_tone="technical",
            source="rule",
        )
    if page.page_type == "flow":
        return SlideDirectorHint(
            slide_key=page.slide_key,
            layout_hint="process-steps",
            animation_type="flow_step",
            target_block_type="flow",
            visual_tone="technical",
            source="rule",
        )
    if page.page_type == "diagram":
        return SlideDirectorHint(
            slide_key=page.slide_key,
            layout_hint="visual-focus",
            animation_type="focus_emphasis",
            target_block_type="diagram_svg",
            visual_tone="spotlight",
            source="rule",
        )
    if page.page_type == "takeaway":
        return SlideDirectorHint(
            slide_key=page.slide_key,
            layout_hint="closing-cta",
            animation_type="focus_emphasis",
            target_block_type="takeaway",
            visual_tone="warm",
            source="rule",
        )

    topic_layouts = ["hero-left", "split-evidence", "insight-stack"]
    return SlideDirectorHint(
        slide_key=page.slide_key,
        layout_hint=topic_layouts[index % len(topic_layouts)],
        animation_type="stagger_reveal",
        target_block_type="key_points",
        visual_tone="editorial" if index % 2 == 0 else "technical",
        source="rule",
    )


def build_slide_director_plan(
    draft: SlideMarkdownDraftResult,
    llm_enabled: bool,
    planner: Callable[[SlideMarkdownDraftPage], dict[str, str]] | None = None,
) -> dict[str, SlideDirectorHint]:
    plan: dict[str, SlideDirectorHint] = {}
    planner_fn = planner or generate_slides_director_hint

    for index, page in enumerate(draft.pages):
        fallback = _fallback_hint(page, index)
        if not llm_enabled:
            plan[page.slide_key] = fallback
            continue

        try:
            hinted = planner_fn(page)
            plan[page.slide_key] = SlideDirectorHint(
                slide_key=page.slide_key,
                layout_hint=hinted.get("layout_hint") or fallback.layout_hint,
                animation_type=hinted.get("animation_type") or fallback.animation_type,
                target_block_type=hinted.get("target_block_type")
                or fallback.target_block_type,
                visual_tone=hinted.get("visual_tone") or fallback.visual_tone,
                source="llm",
            )
        except (LLMRequestError, ValueError, KeyError):
            plan[page.slide_key] = fallback

    tone_set = {hint.visual_tone for hint in plan.values() if hint.visual_tone}
    if len(tone_set) < 2:
        for index, page in enumerate(draft.pages):
            hint = plan.get(page.slide_key)
            if hint is None:
                continue
            if page.page_type == "diagram":
                hint.visual_tone = "spotlight"
            elif page.page_type == "takeaway":
                hint.visual_tone = "warm"
            else:
                hint.visual_tone = "editorial" if index % 2 == 0 else "technical"

    return plan
