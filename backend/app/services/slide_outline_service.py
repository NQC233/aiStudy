from __future__ import annotations

from dataclasses import dataclass

from app.schemas.slide_lesson_plan import AssetLessonPlanPayload, LessonPlanEvidenceAnchor


@dataclass
class SlideOutlineItem:
    slide_key: str
    stage: str
    title: str
    goal: str
    script: str
    page_type: str
    evidence_anchors: list[LessonPlanEvidenceAnchor]


@dataclass
class SlideOutlineResult:
    page_count: int
    pages: list[SlideOutlineItem]


_PAGE_TYPE_BY_STAGE = {
    "problem": ["topic", "comparison"],
    "method": ["topic", "flow"],
    "mechanism": ["topic", "diagram"],
    "experiment": ["comparison", "topic"],
    "conclusion": ["takeaway"],
}


def clamp_page_count(proposed_count: int, minimum: int = 8, maximum: int = 16) -> int:
    return max(minimum, min(maximum, proposed_count))


def _estimate_page_count(lesson_plan: AssetLessonPlanPayload) -> int:
    evidence_count = sum(len(stage.evidence_anchors) for stage in lesson_plan.stages)
    proposed = 8 + evidence_count
    return clamp_page_count(proposed)


def _distribute_pages(total_pages: int, stage_count: int) -> list[int]:
    base = [1] * stage_count
    remaining = max(0, total_pages - stage_count)
    cursor = 0
    while remaining > 0:
        base[cursor % stage_count] += 1
        cursor += 1
        remaining -= 1
    return base


def build_slide_outline(lesson_plan: AssetLessonPlanPayload) -> SlideOutlineResult:
    page_count = _estimate_page_count(lesson_plan)
    stage_distribution = _distribute_pages(page_count, len(lesson_plan.stages))

    pages: list[SlideOutlineItem] = []
    for stage_index, stage in enumerate(lesson_plan.stages):
        stage_pages = stage_distribution[stage_index]
        page_types = _PAGE_TYPE_BY_STAGE.get(stage.stage, ["topic"])
        for local_index in range(stage_pages):
            page_no = len(pages) + 1
            page_type = page_types[local_index % len(page_types)]
            pages.append(
                SlideOutlineItem(
                    slide_key=f"slide:{stage.stage}:{page_no}",
                    stage=stage.stage,
                    title=stage.title if local_index == 0 else f"{stage.title}（续{local_index}）",
                    goal=stage.goal,
                    script=stage.script,
                    page_type=page_type,
                    evidence_anchors=stage.evidence_anchors,
                )
            )

    return SlideOutlineResult(page_count=len(pages), pages=pages)
