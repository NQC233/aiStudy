from __future__ import annotations

from app.schemas.slide_dsl import (
    QualityScoreReport,
    SlideBlock,
    SlideFixLog,
    SlidesDslPayload,
)
from app.schemas.slide_lesson_plan import AssetLessonPlanPayload
from app.services.slide_outline_service import clamp_page_count
from app.services.slide_quality_service import evaluate_slides_quality

_MAX_KEYPOINT_CHARS = 72
_MAX_EVIDENCE_CHARS = 88
_MAX_PAGE_CONTENT_CHARS = 320


def _clip_text(text: str, limit: int) -> str:
    normalized = (text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}..."


def _page_content_chars(page) -> int:
    key_points = next((b for b in page.blocks if b.block_type == "key_points"), None)
    evidence = next((b for b in page.blocks if b.block_type == "evidence"), None)
    key_points_len = sum(len(item) for item in (key_points.items if key_points else []))
    evidence_len = sum(len(item) for item in (evidence.items if evidence else []))
    return key_points_len + evidence_len


def _split_page_if_needed(page):
    key_points = next((b for b in page.blocks if b.block_type == "key_points"), None)
    evidence = next((b for b in page.blocks if b.block_type == "evidence"), None)
    if key_points is None or evidence is None:
        return page, None

    key_points.items = [_clip_text(item, _MAX_KEYPOINT_CHARS) for item in key_points.items][:4]
    evidence.items = [_clip_text(item, _MAX_EVIDENCE_CHARS) for item in evidence.items][:3]

    if _page_content_chars(page) <= _MAX_PAGE_CONTENT_CHARS:
        return page, None
    if len(key_points.items) <= 2 and len(evidence.items) <= 1:
        return page, None

    continuation = page.model_copy(deep=True)
    continuation.slide_key = f"{page.slide_key}:cont"

    move_key_points = key_points.items[2:]
    move_evidence = evidence.items[1:]
    key_points.items = key_points.items[:2]
    evidence.items = evidence.items[:1]

    continuation_key_points = next(
        (b for b in continuation.blocks if b.block_type == "key_points"),
        None,
    )
    continuation_evidence = next(
        (b for b in continuation.blocks if b.block_type == "evidence"),
        None,
    )
    continuation_title = next(
        (b for b in continuation.blocks if b.block_type == "title"),
        None,
    )
    continuation_note = next(
        (b for b in continuation.blocks if b.block_type == "speaker_note"),
        None,
    )

    if continuation_title is not None:
        continuation_title.content = f"{continuation_title.content}（续）"
    if continuation_key_points is not None:
        continuation_key_points.items = move_key_points or continuation_key_points.items[:2]
    if continuation_evidence is not None:
        continuation_evidence.items = move_evidence or continuation_evidence.items[:1]
    if continuation_note is not None:
        continuation_note.content = _clip_text(
            f"延续上一页，先讲补充要点，再结合证据收束。{continuation_note.content}",
            180,
        )

    return page, continuation


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
    inserted_count = 0
    max_pages = clamp_page_count(999)

    for page_index in quality_report.low_quality_pages:
        effective_index = page_index + inserted_count
        if effective_index >= len(updated_pages) or page_index >= len(template_dsl.pages):
            continue
        before_page = updated_pages[effective_index]
        repaired_page = template_dsl.pages[page_index].model_copy(deep=True)
        if _page_content_chars(before_page) > _MAX_PAGE_CONTENT_CHARS:
            repaired_page = before_page.model_copy(deep=True)

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
        repaired_page, continuation_page = _split_page_if_needed(repaired_page)
        updated_pages[effective_index] = repaired_page
        if continuation_page is not None and len(updated_pages) < max_pages:
            updated_pages.insert(effective_index + 1, continuation_page)
            inserted_count += 1

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
                if item.page_index == effective_index
            ),
            0.0,
        )
        fix_logs.append(
            SlideFixLog(
                page_index=effective_index,
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
