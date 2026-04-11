from __future__ import annotations

from app.schemas.slide_dsl import (
    QualityScoreReport,
    SlideBlock,
    SlideFixLog,
    SlidesDslPayload,
)
from app.schemas.slide_lesson_plan import AssetLessonPlanPayload
from app.services.slide_quality_service import evaluate_slides_quality


def repair_low_quality_pages(
    slides_dsl: SlidesDslPayload,
    lesson_plan: AssetLessonPlanPayload,
    quality_report: QualityScoreReport,
) -> tuple[SlidesDslPayload, list[SlideFixLog]]:
    from app.services.slide_dsl_service import build_slides_dsl

    template_dsl = build_slides_dsl(lesson_plan)
    page_score_by_index = {
        item.page_index: item.score for item in quality_report.page_scores
    }

    updated_pages = list(slides_dsl.pages)
    fix_logs: list[SlideFixLog] = []
    for page_index in quality_report.low_quality_pages:
        if page_index >= len(updated_pages) or page_index >= len(template_dsl.pages):
            continue
        before_page = updated_pages[page_index]
        repaired_page = template_dsl.pages[page_index].model_copy(deep=True)

        key_points_block = next(
            (block for block in repaired_page.blocks if block.block_type == "key_points"),
            None,
        )
        evidence_block = next(
            (block for block in repaired_page.blocks if block.block_type == "evidence"),
            None,
        )
        speaker_note_block = next(
            (block for block in repaired_page.blocks if block.block_type == "speaker_note"),
            None,
        )

        if key_points_block and len(key_points_block.items) < 2:
            key_points_block.items.extend(
                [
                    f"补充说明：{repaired_page.stage} 阶段要点一",
                    f"补充说明：{repaired_page.stage} 阶段要点二",
                ]
            )
            key_points_block.items = key_points_block.items[:4]

        if evidence_block and not evidence_block.items:
            evidence_block.items = ["补充证据：请回看原文引用段落。"]

        if speaker_note_block and not speaker_note_block.content.strip():
            speaker_note_block.content = (
                f"强调本页与主线阶段“{repaired_page.stage}”的衔接关系，并结合证据展开讲解。"
            )

        repaired_page.blocks.append(
            SlideBlock(
                block_type="speaker_tip",
                content="先讲结论，再讲证据，最后回扣主线。",
            )
        )
        updated_pages[page_index] = repaired_page

        temp_payload = SlidesDslPayload(
            asset_id=slides_dsl.asset_id,
            version=slides_dsl.version,
            generated_at=slides_dsl.generated_at,
            pages=updated_pages,
        )
        after_report = evaluate_slides_quality(temp_payload)
        after_score = next(
            (
                item.score
                for item in after_report.page_scores
                if item.page_index == page_index
            ),
            0.0,
        )
        fix_logs.append(
            SlideFixLog(
                page_index=page_index,
                slide_key=before_page.slide_key,
                before_score=page_score_by_index.get(page_index, 0.0),
                after_score=after_score,
                reason="quality_score_below_threshold",
            )
        )

    return (
        SlidesDslPayload(
            asset_id=slides_dsl.asset_id,
            version=slides_dsl.version,
            generated_at=slides_dsl.generated_at,
            pages=updated_pages,
        ),
        fix_logs,
    )
