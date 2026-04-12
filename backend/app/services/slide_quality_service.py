from __future__ import annotations

from app.schemas.slide_dsl import (
    MustPassIssue,
    MustPassReport,
    PageQualityScore,
    QualityScoreReport,
    SlidesDslPayload,
)

_TEMPLATE_ALLOWLIST = {
    "topic_deep_dive",
    "comparison_matrix",
    "flow_explain",
    "diagram_explain",
    "takeaway_wrapup",
}

_TITLE_MAX_CHARS = 34
_KEY_POINT_ITEM_MAX_CHARS = 64
_EVIDENCE_ITEM_MAX_CHARS = 96
_SPEAKER_NOTE_MAX_CHARS = 220
_PAGE_DENSITY_MAX_CHARS = 360
_VERBATIM_SNIPPET_MIN_CHARS = 42


def _overflow_risks(page) -> list[str]:
    risks: list[str] = []

    title_block = next((b for b in page.blocks if b.block_type == "title"), None)
    key_points_block = next((b for b in page.blocks if b.block_type == "key_points"), None)
    evidence_block = next((b for b in page.blocks if b.block_type == "evidence"), None)
    speaker_note_block = next((b for b in page.blocks if b.block_type == "speaker_note"), None)

    if title_block and len(title_block.content.strip()) > _TITLE_MAX_CHARS:
        risks.append("title_too_long")

    key_points_items = key_points_block.items if key_points_block else []
    evidence_items = evidence_block.items if evidence_block else []
    if any(len(item.strip()) > _KEY_POINT_ITEM_MAX_CHARS for item in key_points_items):
        risks.append("key_point_too_long")
    if any(len(item.strip()) > _EVIDENCE_ITEM_MAX_CHARS for item in evidence_items):
        risks.append("evidence_too_long")

    density_chars = sum(len(item.strip()) for item in key_points_items) + sum(
        len(item.strip()) for item in evidence_items
    )
    if density_chars > _PAGE_DENSITY_MAX_CHARS:
        risks.append("page_density_too_high")

    if speaker_note_block and len(speaker_note_block.content.strip()) > _SPEAKER_NOTE_MAX_CHARS:
        risks.append("speaker_note_too_long")

    return risks


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _has_verbatim_copy_risk(page) -> bool:
    evidence_block = next((b for b in page.blocks if b.block_type == "evidence"), None)
    key_points_block = next((b for b in page.blocks if b.block_type == "key_points"), None)
    combined_content = _normalize_text(
        " ".join((key_points_block.items if key_points_block else []) + (evidence_block.items if evidence_block else []))
    )
    if not combined_content:
        return False

    for citation in page.citations:
        quote = _normalize_text(citation.quote)
        if len(quote) < _VERBATIM_SNIPPET_MIN_CHARS:
            continue
        probe = quote[: min(len(quote), 96)]
        if probe and probe in combined_content:
            return True
    return False


def validate_slides_must_pass(slides_dsl: SlidesDslPayload) -> MustPassReport:
    issues: list[MustPassIssue] = []
    if len(slides_dsl.pages) < 8 or len(slides_dsl.pages) > 16:
        issues.append(
            MustPassIssue(
                page_index=-1,
                field="page_count",
                code="invalid_page_count",
                message="page_count 必须在 8~16 之间",
            )
        )

    for index, page in enumerate(slides_dsl.pages):
        if page.template_type not in _TEMPLATE_ALLOWLIST:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="template_type",
                    code="invalid_template",
                    message="template_type 不在允许集合中",
                )
            )
        if not page.blocks:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="blocks",
                    code="missing_blocks",
                    message="blocks 不能为空",
                )
            )

        title_blocks = [b for b in page.blocks if b.block_type == "title" and b.content]
        key_point_blocks = [b for b in page.blocks if b.block_type == "key_points"]
        evidence_blocks = [b for b in page.blocks if b.block_type == "evidence"]
        speaker_note_blocks = [b for b in page.blocks if b.block_type == "speaker_note"]

        if len(title_blocks) != 1:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="title",
                    code="invalid_title_count",
                    message="每页必须且仅能有一个 title",
                )
            )

        overflow_risks = _overflow_risks(page)
        if overflow_risks:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="layout_fit",
                    code="overflow_risk",
                    message=f"存在视口溢出风险: {', '.join(overflow_risks)}",
                )
            )

        key_points_count = len(key_point_blocks[0].items) if key_point_blocks else 0
        if key_points_count < 2 or key_points_count > 4:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="key_points",
                    code="invalid_key_points_density",
                    message="key_points 条数必须在 2~4",
                )
            )

        evidence_count = len(evidence_blocks[0].items) if evidence_blocks else 0
        if evidence_count < 1:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="evidence",
                    code="missing_evidence",
                    message="每页至少一个 evidence",
                )
            )

        has_speaker_note = bool(
            speaker_note_blocks and speaker_note_blocks[0].content.strip()
        )
        if not has_speaker_note:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="speaker_note",
                    code="missing_speaker_note",
                    message="speaker_note 不得为空",
                )
            )

        if not page.citations:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="citations",
                    code="missing_citations",
                    message="citations 不能为空",
                )
            )

        if _has_verbatim_copy_risk(page):
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="content_rewrite",
                    code="verbatim_copy_risk",
                    message="展示内容疑似直接复制引用原文，需改写为讲解表达。",
                )
            )
        for citation in page.citations:
            if citation.page_no < 1 or not citation.block_ids:
                issues.append(
                    MustPassIssue(
                        page_index=index,
                        field="citations",
                        code="invalid_citation_anchor",
                        message="citation 必须包含有效 page_no 与 block_ids",
                    )
                )

    return MustPassReport(passed=len(issues) == 0, issues=issues)


def _score_page_density(key_points_count: int, evidence_count: int) -> float:
    score = 0.0
    if 2 <= key_points_count <= 4:
        score += 25.0
    elif key_points_count == 1:
        score += 10.0

    if evidence_count >= 1:
        score += 20.0
    return score


def evaluate_slides_quality(
    slides_dsl: SlidesDslPayload,
    threshold: float = 70.0,
) -> QualityScoreReport:
    page_scores: list[PageQualityScore] = []
    duplicate_key_count: dict[str, int] = {}

    normalized_content: list[str] = []
    for page in slides_dsl.pages:
        key = " ".join(
            [
                " ".join(block.items).strip().lower()
                if block.items
                else block.content.strip().lower()
                for block in page.blocks
                if block.block_type in {"key_points", "evidence", "speaker_note"}
            ]
        )
        normalized_content.append(key)
        duplicate_key_count[key] = duplicate_key_count.get(key, 0) + 1

    for index, page in enumerate(slides_dsl.pages):
        reasons: list[str] = []
        score = 0.0

        key_points_block = next(
            (block for block in page.blocks if block.block_type == "key_points"),
            None,
        )
        evidence_block = next(
            (block for block in page.blocks if block.block_type == "evidence"),
            None,
        )
        speaker_note_block = next(
            (block for block in page.blocks if block.block_type == "speaker_note"),
            None,
        )

        key_points_count = len(key_points_block.items) if key_points_block else 0
        evidence_count = len(evidence_block.items) if evidence_block else 0

        score += _score_page_density(key_points_count, evidence_count)
        if len(page.citations) >= 1:
            score += 25.0
        else:
            reasons.append("缺少引用锚点")

        speaker_note_text = speaker_note_block.content.strip() if speaker_note_block else ""
        if speaker_note_text:
            note_len = len(speaker_note_text)
            score += 25.0 if note_len >= 18 else 12.0
        else:
            reasons.append("讲稿缺失")

        evidence_key = normalized_content[index]
        if duplicate_key_count.get(evidence_key, 0) > 1:
            score -= 10.0
            reasons.append("与其他页面内容重复度较高")

        overflow_risks = _overflow_risks(page)
        if overflow_risks:
            score -= 35.0
            reasons.append(f"存在视口溢出风险: {', '.join(overflow_risks)}")

        if _has_verbatim_copy_risk(page):
            score -= 20.0
            reasons.append("展示内容疑似直接复制引用原文")

        if not reasons:
            reasons.append("质量达标")

        page_scores.append(
            PageQualityScore(
                page_index=index,
                slide_key=page.slide_key,
                score=max(0.0, min(100.0, score)),
                reasons=reasons,
            )
        )

    overall = 0.0
    if page_scores:
        overall = sum(item.score for item in page_scores) / len(page_scores)

    low_quality_pages = [
        item.page_index for item in page_scores if item.score < threshold
    ]
    return QualityScoreReport(
        overall_score=round(overall, 2),
        page_scores=page_scores,
        low_quality_pages=low_quality_pages,
    )
