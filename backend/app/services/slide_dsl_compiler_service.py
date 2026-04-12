from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from app.schemas.slide_dsl import (
    SlideAnimation,
    SlideBlock,
    SlideCitation,
    SlidePageDsl,
    SlidesDslPayload,
)
from app.schemas.slide_lesson_plan import AssetLessonPlanPayload
from app.services.slide_director_plan_service import SlideDirectorHint
from app.services.slide_markdown_service import SlideMarkdownDraftResult


_TEMPLATE_BY_PAGE_TYPE = {
    "topic": "topic_deep_dive",
    "comparison": "comparison_matrix",
    "flow": "flow_explain",
    "diagram": "diagram_explain",
    "takeaway": "takeaway_wrapup",
}

_ANIMATION_BY_PAGE_TYPE: dict[
    str,
    Literal[
        "stagger_reveal",
        "focus_emphasis",
        "compare_switch",
        "flow_step",
    ],
] = {
    "topic": "stagger_reveal",
    "comparison": "compare_switch",
    "flow": "flow_step",
    "diagram": "focus_emphasis",
    "takeaway": "focus_emphasis",
}


def _build_comparison_rows(
    key_points: list[str],
    evidence: list[str],
) -> list[list[str]]:
    baseline = key_points[0] if key_points else "基线方法"
    candidate = key_points[1] if len(key_points) > 1 else "本方法"
    evidence_text = evidence[0] if evidence else "证据补齐中"
    return [
        ["基线", baseline, "中等"],
        ["本方法", candidate, "更优"],
        ["证据", evidence_text, "可回跳"],
    ]


def _build_flow_steps(
    key_points: list[str],
) -> list[str]:
    if len(key_points) >= 3:
        return key_points[:4]
    default_steps = ["输入预处理", "核心模块计算", "结果聚合输出"]
    return [*key_points, *default_steps][:4]


def _diagram_svg_placeholder(title: str) -> str:
    safe_title = title.replace("<", "").replace(">", "")
    return (
        "<svg viewBox='0 0 360 160' xmlns='http://www.w3.org/2000/svg'>"
        "<rect x='8' y='8' width='344' height='144' rx='12' fill='#f5efe4' stroke='#b27d3a'/>"
        "<circle cx='70' cy='80' r='24' fill='#d9b98d'/>"
        "<rect x='130' y='58' width='90' height='44' rx='8' fill='#ead7b8'/>"
        "<rect x='248' y='58' width='70' height='44' rx='8' fill='#f2e6d1'/>"
        "<path d='M94 80 L130 80' stroke='#8f6126' stroke-width='3'/>"
        "<path d='M220 80 L248 80' stroke='#8f6126' stroke-width='3'/>"
        f"<text x='20' y='150' font-size='12' fill='#5f3f1a'>{safe_title}</text>"
        "</svg>"
    )


def compile_markdown_draft_to_slides_dsl(
    lesson_plan: AssetLessonPlanPayload,
    draft: SlideMarkdownDraftResult,
    director_plan: dict[str, SlideDirectorHint] | None = None,
) -> SlidesDslPayload:
    stage_to_anchors = {stage.stage: stage.evidence_anchors for stage in lesson_plan.stages}

    pages: list[SlidePageDsl] = []
    for draft_page in draft.pages:
        hint = (director_plan or {}).get(draft_page.slide_key)
        citations = [
            SlideCitation(
                page_no=anchor.page_no,
                block_ids=anchor.block_ids,
                quote=anchor.quote,
            )
            for anchor in stage_to_anchors.get(draft_page.stage, [])
            if anchor.quote
        ]
        if not citations:
            citations = [SlideCitation(page_no=1, block_ids=["fallback"], quote="证据补齐中")]

        blocks = [
            SlideBlock(block_type="title", content=draft_page.title),
            SlideBlock(block_type="key_points", items=draft_page.key_points),
            SlideBlock(block_type="evidence", items=draft_page.evidence),
            SlideBlock(block_type="speaker_note", content=draft_page.speaker_note),
            SlideBlock(block_type="takeaway", content=draft_page.takeaway),
        ]

        if draft_page.page_type == "comparison":
            comparison_rows = _build_comparison_rows(
                draft_page.key_points,
                draft_page.evidence,
            )
            blocks.append(
                SlideBlock(
                    block_type="comparison",
                    meta={
                        "columns": ["方案", "说明", "结论"],
                        "rows": comparison_rows,
                    },
                )
            )

        if draft_page.page_type == "flow":
            flow_steps = _build_flow_steps(draft_page.key_points)
            blocks.append(
                SlideBlock(
                    block_type="flow",
                    meta={
                        "steps": flow_steps,
                    },
                )
            )

        if draft_page.page_type == "diagram":
            blocks.append(
                SlideBlock(
                    block_type="diagram_svg",
                    svg_content=_diagram_svg_placeholder(draft_page.title),
                )
            )

        animation_type = _ANIMATION_BY_PAGE_TYPE.get(
            draft_page.page_type,
            "stagger_reveal",
        )
        if hint and hint.animation_type in {
            "stagger_reveal",
            "focus_emphasis",
            "compare_switch",
            "flow_step",
        }:
            animation_type = hint.animation_type

        target_block_type = hint.target_block_type if hint else "key_points"
        pages.append(
            SlidePageDsl(
                slide_key=draft_page.slide_key,
                stage=draft_page.stage,
                page_type=draft_page.page_type,
                layout_hint=hint.layout_hint if hint else "hero-left",
                director_source=hint.source if hint else "rule",
                visual_tone=hint.visual_tone if hint else "technical",
                template_type=_TEMPLATE_BY_PAGE_TYPE.get(draft_page.page_type, "topic_deep_dive"),
                animation_preset=animation_type,
                animations=[
                    SlideAnimation(
                        animation_type=animation_type,
                        target_block_type=target_block_type,
                        cue_key=f"{draft_page.slide_key}:{target_block_type}",
                    )
                ],
                blocks=blocks,
                citations=citations,
            )
        )

    return SlidesDslPayload(
        schema_version="2",
        asset_id=lesson_plan.asset_id,
        version=lesson_plan.version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        pages=pages,
    )
