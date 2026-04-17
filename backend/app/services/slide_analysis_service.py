from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from app.schemas.document_chunk import AssetRetrievalSearchResponse
from app.schemas.document_chunk import RetrievalSearchHit


@dataclass(frozen=True)
class SlideQueryFamily:
    key: str
    query: str


@dataclass
class SlideAnalysisPack:
    query_family_hits: dict[str, list[RetrievalSearchHit]]
    document_outline: list[str]
    problem_statements: list[str]
    method_components: list[str]
    method_steps: list[str]
    key_formulas: list[str]
    datasets_metrics: list[str]
    main_results: list[str]
    ablations: list[str]
    limitations: list[str]
    evidence_catalog: list[dict[str, object]]


DEFAULT_SLIDE_QUERY_FAMILIES = [
    SlideQueryFamily("paper_motivation", "research problem and motivation"),
    SlideQueryFamily("method_overview", "method overview and framework"),
    SlideQueryFamily("method_steps", "method stages modules pipeline"),
    SlideQueryFamily("key_formulas", "objective loss formula equation"),
    SlideQueryFamily("datasets_metrics", "datasets metrics evaluation setup"),
    SlideQueryFamily(
        "main_experiment_results", "main experiment results performance"
    ),
    SlideQueryFamily("ablations_comparisons", "ablation comparison baseline"),
    SlideQueryFamily("limitations_future_work", "limitations future work"),
    SlideQueryFamily(
        "figures_worth_showing", "important figures diagrams architecture"
    ),
    SlideQueryFamily("tables_worth_showing", "important result tables metrics"),
]


def _is_low_signal_text(text: str) -> bool:
    normalized = " ".join((text or "").split()).strip().lower()
    if not normalized:
        return True

    blocked_prefixes = ("attention is all you need", "copyright", "references")
    blocked_substrings = (
        "grants permission to reproduce the tables and figures",
        "provided proper attribution is provided",
        "arxiv preprint",
    )
    is_reference_entry = normalized.startswith("[") and "et al." in normalized
    is_section_heading = bool(re.fullmatch(r"\d+(?:\.\d+)*\s+[a-z][a-z\s-]{1,40}", normalized))
    author_markers = ("google brain", "google research", "university of toronto", "@google.com")
    author_marker_hits = sum(1 for marker in author_markers if marker in normalized)
    is_author_list = normalized.count("\n") >= 2 and author_marker_hits >= 1
    return (
        normalized.startswith(blocked_prefixes)
        or any(token in normalized for token in blocked_substrings)
        or is_reference_entry
        or is_section_heading
        or is_author_list
        or len(normalized) < 24
    )


def filter_slide_retrieval_hits(hits: list[RetrievalSearchHit]) -> list[RetrievalSearchHit]:
    filtered: list[RetrievalSearchHit] = []
    seen_chunk_ids: set[str] = set()

    for hit in hits:
        if hit.chunk_id in seen_chunk_ids:
            continue
        if _is_low_signal_text(hit.text):
            continue
        filtered.append(hit)
        seen_chunk_ids.add(hit.chunk_id)

    return filtered


def summarize_slide_analysis_pack(
    grouped_hits: dict[str, list[RetrievalSearchHit]],
) -> SlideAnalysisPack:
    filtered_hits = {
        key: filter_slide_retrieval_hits(value) for key, value in grouped_hits.items()
    }
    evidence_catalog: list[dict[str, object]] = []
    for family_key, hits in filtered_hits.items():
        for hit in hits:
            evidence_catalog.append(
                {
                    "family_key": family_key,
                    "chunk_id": hit.chunk_id,
                    "page_start": hit.page_start,
                    "page_end": hit.page_end,
                    "block_ids": list(hit.block_ids or []),
                    "section_path": list(hit.section_path or []),
                    "quote_text": hit.quote_text,
                }
            )

    return SlideAnalysisPack(
        query_family_hits=filtered_hits,
        document_outline=[
            " / ".join(hit.section_path)
            for hits in filtered_hits.values()
            for hit in hits
            if hit.section_path
        ],
        problem_statements=[
            hit.text for hit in filtered_hits.get("paper_motivation", [])
        ],
        method_components=[
            hit.text for hit in filtered_hits.get("method_overview", [])
        ],
        method_steps=[hit.text for hit in filtered_hits.get("method_steps", [])],
        key_formulas=[hit.text for hit in filtered_hits.get("key_formulas", [])],
        datasets_metrics=[
            hit.text for hit in filtered_hits.get("datasets_metrics", [])
        ],
        main_results=[
            hit.text for hit in filtered_hits.get("main_experiment_results", [])
        ],
        ablations=[
            hit.text for hit in filtered_hits.get("ablations_comparisons", [])
        ],
        limitations=[
            hit.text for hit in filtered_hits.get("limitations_future_work", [])
        ],
        evidence_catalog=evidence_catalog,
    )


def refine_slide_analysis_pack(
    analysis_pack: SlideAnalysisPack,
    *,
    refine_func: Callable[[str, list[RetrievalSearchHit]], list[RetrievalSearchHit]] | None = None,
) -> SlideAnalysisPack:
    if refine_func is None:
        return analysis_pack

    refined_hits: dict[str, list[RetrievalSearchHit]] = {}
    for family_key, hits in analysis_pack.query_family_hits.items():
        candidate_hits = refine_func(family_key, list(hits))
        filtered_candidate_hits = filter_slide_retrieval_hits(candidate_hits)
        refined_hits[family_key] = filtered_candidate_hits or list(hits)
    return summarize_slide_analysis_pack(refined_hits)


def build_slide_analysis_pack(
    query_families: list[SlideQueryFamily],
    *,
    search_func: Callable[[str], list[RetrievalSearchHit]],
    refine_func: Callable[[str, list[RetrievalSearchHit]], list[RetrievalSearchHit]] | None = None,
) -> SlideAnalysisPack:
    grouped_hits: dict[str, list[RetrievalSearchHit]] = {}
    for family in query_families:
        grouped_hits[family.key] = search_func(family.query)
    return refine_slide_analysis_pack(
        summarize_slide_analysis_pack(grouped_hits),
        refine_func=refine_func,
    )


def build_asset_slide_analysis_pack(
    asset_id: str,
    query_families: list[SlideQueryFamily] | None = None,
    *,
    top_k: int = 3,
    rewrite_query: bool = False,
    strategy: str = "s0",
    search_func: Callable[
        [str, str, int, bool, str], AssetRetrievalSearchResponse
    ],
    refine_func: Callable[[str, list[RetrievalSearchHit]], list[RetrievalSearchHit]] | None = None,
) -> SlideAnalysisPack:
    families = query_families or DEFAULT_SLIDE_QUERY_FAMILIES
    return build_slide_analysis_pack(
        families,
        search_func=lambda query: search_func(
            asset_id,
            query,
            top_k,
            rewrite_query,
            strategy,
        ).results,
        refine_func=refine_func,
    )
