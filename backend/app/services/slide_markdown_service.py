from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.slide_outline_service import SlideOutlineResult


@dataclass
class SlideMarkdownDraftPage:
    slide_key: str
    stage: str
    page_type: str
    title: str
    key_points: list[str]
    evidence: list[str]
    speaker_note: str
    takeaway: str
    markdown: str


@dataclass
class SlideMarkdownDraftResult:
    pages: list[SlideMarkdownDraftPage]


def _normalize_goal(goal: str) -> str:
    text = (goal or "").strip()
    if not text:
        return ""

    if "阶段讲解" in text or "学习者" in text or text.startswith("完成“"):
        return ""

    for prefix in ["说明", "解释", "展示", "总结", "归纳", "明确"]:
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix) :].strip("：:，,。 ")
    return text


def _clean_evidence_text(text: str) -> str:
    cleaned = (text or "").replace("；", " ").strip()
    if len(cleaned) > 96:
        return f"{cleaned[:95].rstrip()}..."
    return cleaned


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    ascii_count = sum(1 for char in text if ord(char) < 128)
    return ascii_count / max(len(text), 1)


def _distill_evidence_text(text: str, title: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return "原文证据仍在补齐，请回看引用段落。"

    english_heavy = _ascii_ratio(normalized) >= 0.45
    if english_heavy:
        compact_title = title.strip() or "本页"
        return f"原文证据支持“{compact_title}”的核心结论（详见引用）。"

    cleaned = normalized.replace("；", " ").strip()
    if len(cleaned) > 72:
        cleaned = f"{cleaned[:71].rstrip()}（详见引用）"
    return cleaned


def _page_type_insight(page_type: str, title: str) -> str:
    if page_type == "comparison":
        return f"{title}突出基线与本方法在核心指标上的差异。"
    if page_type == "flow":
        return f"{title}按照输入、计算、输出顺序组织讲解。"
    if page_type == "diagram":
        return f"{title}通过图示强调模块关系与信息流方向。"
    if page_type == "takeaway":
        return f"{title}收束贡献边界，并给出下一步工作方向。"
    return f"{title}将结论和证据建立对应关系。"


def _build_key_points(goal: str, page_type: str, title: str, evidence: list[str]) -> list[str]:
    normalized_goal = _normalize_goal(goal)
    primary_evidence = _clean_evidence_text(evidence[0]) if evidence else "实验与原文证据支持当前结论。"
    first_point = (
        f"{title}：{normalized_goal}"
        if normalized_goal
        else f"{title}页聚焦核心结论与关键证据。"
    )
    points = [
        first_point,
        primary_evidence,
    ]
    if len(evidence) > 1:
        secondary = _clean_evidence_text(evidence[1])
        if secondary and secondary != primary_evidence:
            points.append(secondary)

    points.append(_page_type_insight(page_type, title))
    return points[:4]


def build_slide_markdown_draft(outline: SlideOutlineResult) -> SlideMarkdownDraftResult:
    pages: list[SlideMarkdownDraftPage] = []
    for item in outline.pages:
        raw_evidence = [anchor.quote for anchor in item.evidence_anchors if anchor.quote][:2]
        evidence = [_distill_evidence_text(quote, item.title) for quote in raw_evidence if quote]
        if not evidence:
            evidence = ["补充证据：请回看原文对应段落。"]
        key_points = _build_key_points(item.goal, item.page_type, item.title, evidence)
        speaker_note = item.script or f"围绕“{item.title}”进行讲解，并和上一页建立衔接。"
        takeaway = f"围绕“{item.stage}”阶段形成可复述结论。"
        markdown = "\n".join(
            [
                f"# {item.title}",
                "",
                "## Key Points",
                *[f"- {point}" for point in key_points],
                "",
                "## Evidence",
                *[f"- {quote}" for quote in evidence],
                "",
                "## Speaker Note",
                speaker_note,
                "",
                "## Takeaway",
                takeaway,
            ]
        )
        pages.append(
            SlideMarkdownDraftPage(
                slide_key=item.slide_key,
                stage=item.stage,
                page_type=item.page_type,
                title=item.title,
                key_points=key_points,
                evidence=evidence,
                speaker_note=speaker_note,
                takeaway=takeaway,
                markdown=markdown,
            )
        )
    return SlideMarkdownDraftResult(pages=pages)
