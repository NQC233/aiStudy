from __future__ import annotations

from app.schemas.slide_dsl import (
    MustPassIssue,
    MustPassReport,
    PageQualityScore,
    QualityScoreReport,
    SlidesDslPayload,
)

_TEMPLATE_ALLOWLIST = {
    "problem_statement",
    "method_overview",
    "mechanism_deep_dive",
    "experiment_results",
    "conclusion_takeaways",
    "generic_explain",
}


def validate_slides_must_pass(slides_dsl: SlidesDslPayload) -> MustPassReport:
    issues: list[MustPassIssue] = []
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
        if not page.citations:
            issues.append(
                MustPassIssue(
                    page_index=index,
                    field="citations",
                    code="missing_citations",
                    message="citations 不能为空",
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


def _score_page_density(block_count: int) -> float:
    if block_count >= 4:
        return 30.0
    if block_count == 3:
        return 22.0
    if block_count == 2:
        return 14.0
    return 6.0


def evaluate_slides_quality(
    slides_dsl: SlidesDslPayload,
    threshold: float = 70.0,
) -> QualityScoreReport:
    page_scores: list[PageQualityScore] = []
    duplicate_key_count: dict[str, int] = {}

    normalized_evidence: list[str] = []
    for page in slides_dsl.pages:
        evidence_content = " ".join(
            block.content.strip().lower()
            for block in page.blocks
            if block.block_type in {"evidence", "goal", "script"}
        )
        normalized_evidence.append(evidence_content)
        duplicate_key_count[evidence_content] = (
            duplicate_key_count.get(evidence_content, 0) + 1
        )

    for index, page in enumerate(slides_dsl.pages):
        reasons: list[str] = []
        score = 0.0

        score += _score_page_density(len(page.blocks))
        if len(page.citations) >= 1:
            score += 30.0
        else:
            reasons.append("缺少引用锚点")

        has_goal = any(
            block.block_type == "goal" and block.content for block in page.blocks
        )
        has_script = any(
            block.block_type == "script" and block.content for block in page.blocks
        )
        if has_goal and has_script:
            score += 25.0
        else:
            reasons.append("讲解目标或讲稿缺失")

        evidence_key = normalized_evidence[index]
        if duplicate_key_count.get(evidence_key, 0) > 1:
            score -= 10.0
            reasons.append("与其他页面内容重复度较高")

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
