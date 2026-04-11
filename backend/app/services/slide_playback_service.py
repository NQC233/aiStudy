from __future__ import annotations

from typing import Literal

from app.schemas.slide_dsl import (
    SlideCueItem,
    SlidePlaybackPagePlan,
    SlidePlaybackPlan,
    SlidesDslPayload,
    SlideTtsManifest,
    SlideTtsManifestItem,
)


def _estimate_page_duration_ms(script: str) -> int:
    text = script.strip()
    if not text:
        return 3000
    return max(3000, min(30000, len(text) * 220))


def _extract_script(page) -> str:
    for block in page.blocks:
        if block.block_type in {"speaker_note", "script"}:
            return block.content
    return ""


def build_tts_manifest_placeholders(slides_dsl: SlidesDslPayload) -> SlideTtsManifest:
    pages: list[SlideTtsManifestItem] = []
    for page in slides_dsl.pages:
        pages.append(
            SlideTtsManifestItem(
                slide_key=page.slide_key,
                duration_ms=_estimate_page_duration_ms(_extract_script(page)),
                status="pending",
            )
        )
    return SlideTtsManifest(pages=pages)


def build_playback_plan_from_slides(slides_dsl: SlidesDslPayload) -> SlidePlaybackPlan:
    pages: list[SlidePlaybackPagePlan] = []
    timeline_cursor = 0

    for page_index, page in enumerate(slides_dsl.pages):
        page_duration = _estimate_page_duration_ms(_extract_script(page))
        cue_count = max(1, len(page.blocks))
        cue_span = max(1, page_duration // cue_count)

        cues: list[SlideCueItem] = []
        for block_index, block in enumerate(page.blocks):
            cue_start = block_index * cue_span
            cue_end = (
                page_duration
                if block_index == cue_count - 1
                else min(page_duration, (block_index + 1) * cue_span)
            )
            cues.append(
                SlideCueItem(
                    block_id=f"{page.slide_key}:{block.block_type}:{block_index + 1}",
                    start_ms=cue_start,
                    end_ms=max(cue_start + 1, cue_end),
                    animation=page.animation_preset,
                )
            )

        pages.append(
            SlidePlaybackPagePlan(
                slide_key=page.slide_key,
                start_ms=timeline_cursor,
                end_ms=timeline_cursor + page_duration,
                duration_ms=page_duration,
                cues=cues,
            )
        )
        timeline_cursor += page_duration

    return SlidePlaybackPlan(total_duration_ms=timeline_cursor, pages=pages)


def resolve_tts_status(
    page_statuses: list[str],
) -> Literal["not_generated", "processing", "ready", "failed", "partial"]:
    if not page_statuses:
        return "not_generated"

    unique_statuses = set(page_statuses)
    if "processing" in unique_statuses or "pending" in unique_statuses:
        return "processing"
    if unique_statuses == {"ready"}:
        return "ready"
    if unique_statuses == {"failed"}:
        return "failed"
    return "partial"
