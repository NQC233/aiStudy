import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.document_chunk import AssetRetrievalSearchResponse
from app.schemas.document_chunk import RetrievalSearchHit
from app.services.slide_analysis_service import (
    DEFAULT_SLIDE_QUERY_FAMILIES,
    SlideQueryFamily,
    build_asset_slide_analysis_pack,
    build_slide_analysis_pack,
    filter_slide_retrieval_hits,
    refine_slide_analysis_pack,
    summarize_slide_analysis_pack,
)


class SlideAnalysisServiceTestCase(unittest.TestCase):
    def test_filter_slide_retrieval_hits_removes_low_signal_entries(self) -> None:
        hits = [
            RetrievalSearchHit(
                chunk_id="c1",
                score=0.91,
                text="Attention Is All You Need",
                page_start=1,
                page_end=1,
                block_ids=["b1"],
                section_path=["Title"],
                quote_text="Attention Is All You Need",
            ),
            RetrievalSearchHit(
                chunk_id="c2",
                score=0.89,
                text="Our model improves BLEU by 2.0 over the previous best system.",
                page_start=8,
                page_end=8,
                block_ids=["b2"],
                section_path=["Results"],
                quote_text="Our model improves BLEU by 2.0 over the previous best system.",
            ),
        ]

        filtered = filter_slide_retrieval_hits(hits)

        self.assertEqual([item.chunk_id for item in filtered], ["c2"])

    def test_filter_slide_retrieval_hits_removes_reference_and_permission_noise(self) -> None:
        hits = [
            RetrievalSearchHit(
                chunk_id="c-ref",
                score=0.82,
                text="[32] Noam Shazeer et al. Outrageously large neural networks.",
                page_start=12,
                page_end=12,
                block_ids=["b-ref"],
                section_path=["References"],
                quote_text="[32] Noam Shazeer et al. Outrageously large neural networks.",
            ),
            RetrievalSearchHit(
                chunk_id="c-permission",
                score=0.81,
                text="Provided proper attribution is provided, Google hereby grants permission to reproduce the tables and figures in this paper.",
                page_start=13,
                page_end=13,
                block_ids=["b-permission"],
                section_path=["Appendix"],
                quote_text="Provided proper attribution is provided, Google hereby grants permission to reproduce the tables and figures in this paper.",
            ),
            RetrievalSearchHit(
                chunk_id="c-good",
                score=0.9,
                text="Table 2 summarizes the BLEU improvement and training cost comparison across architectures.",
                page_start=8,
                page_end=8,
                block_ids=["b-good"],
                section_path=["Results"],
                quote_text="Table 2 summarizes the BLEU improvement and training cost comparison across architectures.",
            ),
        ]

        filtered = filter_slide_retrieval_hits(hits)

        self.assertEqual([item.chunk_id for item in filtered], ["c-good"])

    def test_filter_slide_retrieval_hits_removes_author_lists_and_section_heading_noise(self) -> None:
        hits = [
            RetrievalSearchHit(
                chunk_id="c-heading",
                score=0.91,
                text="6 Results",
                page_start=8,
                page_end=8,
                block_ids=["b-heading"],
                section_path=["Attention Is All You Need", "6 Results"],
                quote_text="6 Results",
            ),
            RetrievalSearchHit(
                chunk_id="c-authors",
                score=0.9,
                text="Attention Is All You Need\nAshish Vaswani Google Brain\nNoam Shazeer Google Brain",
                page_start=1,
                page_end=1,
                block_ids=["b-authors"],
                section_path=["Attention Is All You Need"],
                quote_text="Attention Is All You Need\nAshish Vaswani Google Brain\nNoam Shazeer Google Brain",
            ),
            RetrievalSearchHit(
                chunk_id="c-good",
                score=0.88,
                text="Recurrent models preclude parallelization and limit training efficiency on long sequences.",
                page_start=2,
                page_end=2,
                block_ids=["b-good"],
                section_path=["Introduction"],
                quote_text="Recurrent models preclude parallelization and limit training efficiency on long sequences.",
            ),
        ]

        filtered = filter_slide_retrieval_hits(hits)

        self.assertEqual([item.chunk_id for item in filtered], ["c-good"])

    def test_summarize_slide_analysis_pack_groups_hits_by_query_family(self) -> None:
        grouped_hits = {
            "paper_motivation": [
                RetrievalSearchHit(
                    chunk_id="c2",
                    score=0.9,
                    text="Recurrent models limit parallelization and slow training on long sequences.",
                    page_start=2,
                    page_end=2,
                    block_ids=["b2"],
                    section_path=["Introduction"],
                    quote_text="Recurrent models limit parallelization and slow training on long sequences.",
                )
            ],
            "method_overview": [
                RetrievalSearchHit(
                    chunk_id="c3",
                    score=0.91,
                    text="The Transformer relies entirely on self-attention without recurrence.",
                    page_start=3,
                    page_end=3,
                    block_ids=["b3"],
                    section_path=["Model Architecture"],
                    quote_text="The Transformer relies entirely on self-attention without recurrence.",
                )
            ],
            "main_experiment_results": [
                RetrievalSearchHit(
                    chunk_id="c9",
                    score=0.93,
                    text="Transformer achieves state-of-the-art BLEU on WMT14 En-De.",
                    page_start=8,
                    page_end=8,
                    block_ids=["b9"],
                    section_path=["Results"],
                    quote_text="Transformer achieves state-of-the-art BLEU on WMT14 En-De.",
                )
            ]
        }

        pack = summarize_slide_analysis_pack(grouped_hits)

        self.assertIn("main_experiment_results", pack.query_family_hits)
        self.assertEqual(pack.query_family_hits["main_experiment_results"][0].chunk_id, "c9")
        self.assertEqual(
            pack.problem_statements,
            ["Recurrent models limit parallelization and slow training on long sequences."],
        )
        self.assertEqual(
            pack.method_components,
            ["The Transformer relies entirely on self-attention without recurrence."],
        )
        self.assertEqual(
            pack.main_results,
            ["Transformer achieves state-of-the-art BLEU on WMT14 En-De."],
        )
        self.assertEqual(pack.evidence_catalog[0]["family_key"], "paper_motivation")
        self.assertEqual(pack.evidence_catalog[-1]["chunk_id"], "c9")

    def test_default_query_families_include_visual_queries(self) -> None:
        keys = [item.key for item in DEFAULT_SLIDE_QUERY_FAMILIES]

        self.assertIn("figures_worth_showing", keys)
        self.assertIn("tables_worth_showing", keys)

    def test_build_slide_analysis_pack_executes_query_families_and_filters_hits(self) -> None:
        families = [
            SlideQueryFamily("paper_motivation", "research problem and motivation"),
            SlideQueryFamily("main_experiment_results", "main experiment results performance"),
        ]

        def _search(query: str) -> list[RetrievalSearchHit]:
            if query == "research problem and motivation":
                return [
                    RetrievalSearchHit(
                        chunk_id="c-title",
                        score=0.95,
                        text="Attention Is All You Need",
                        page_start=1,
                        page_end=1,
                        block_ids=["b-title"],
                        section_path=["Title"],
                        quote_text="Attention Is All You Need",
                    ),
                    RetrievalSearchHit(
                        chunk_id="c-problem",
                        score=0.87,
                        text="Recurrent models limit parallelization and slow training on long sequences.",
                        page_start=2,
                        page_end=2,
                        block_ids=["b-problem"],
                        section_path=["Introduction"],
                        quote_text="Recurrent models limit parallelization and slow training on long sequences.",
                    ),
                ]
            return [
                RetrievalSearchHit(
                    chunk_id="c-result",
                    score=0.91,
                    text="Transformer achieves state-of-the-art BLEU on WMT14 En-De.",
                    page_start=8,
                    page_end=8,
                    block_ids=["b-result"],
                    section_path=["Results"],
                    quote_text="Transformer achieves state-of-the-art BLEU on WMT14 En-De.",
                )
            ]

        pack = build_slide_analysis_pack(families, search_func=_search)

        self.assertEqual(
            [hit.chunk_id for hit in pack.query_family_hits["paper_motivation"]],
            ["c-problem"],
        )
        self.assertEqual(
            [hit.chunk_id for hit in pack.query_family_hits["main_experiment_results"]],
            ["c-result"],
        )

    def test_build_asset_slide_analysis_pack_uses_retrieval_contract(self) -> None:
        calls: list[tuple[str, str, int, bool, str]] = []

        def _search(
            asset_id: str,
            query: str,
            top_k: int,
            rewrite_query: bool,
            strategy: str,
        ) -> AssetRetrievalSearchResponse:
            calls.append((asset_id, query, top_k, rewrite_query, strategy))
            return AssetRetrievalSearchResponse(
                asset_id=asset_id,
                query=query,
                top_k=top_k,
                results=[
                    RetrievalSearchHit(
                        chunk_id=f"hit-{query}",
                        score=0.9,
                        text="The model improves translation quality over strong baselines.",
                        page_start=8,
                        page_end=8,
                        block_ids=["block-1"],
                        section_path=["Results"],
                        quote_text="The model improves translation quality over strong baselines.",
                    )
                ],
            )

        families = [
            SlideQueryFamily("paper_motivation", "research problem and motivation"),
            SlideQueryFamily("main_experiment_results", "main experiment results performance"),
        ]

        pack = build_asset_slide_analysis_pack(
            asset_id="asset-123",
            query_families=families,
            top_k=3,
            rewrite_query=True,
            strategy="s3",
            search_func=_search,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0],
            ("asset-123", "research problem and motivation", 3, True, "s3"),
        )
        self.assertEqual(
            [hit.chunk_id for hit in pack.query_family_hits["main_experiment_results"]],
            ["hit-main experiment results performance"],
        )

    def test_refine_slide_analysis_pack_applies_model_side_pruning(self) -> None:
        grouped_hits = {
            "paper_motivation": [
                RetrievalSearchHit(
                    chunk_id="c-heading",
                    score=0.9,
                    text="6 Results",
                    page_start=8,
                    page_end=8,
                    block_ids=["b-heading"],
                    section_path=["Results"],
                    quote_text="6 Results",
                ),
                RetrievalSearchHit(
                    chunk_id="c-problem",
                    score=0.88,
                    text="Recurrent models limit parallelization on long sequences.",
                    page_start=2,
                    page_end=2,
                    block_ids=["b-problem"],
                    section_path=["Introduction"],
                    quote_text="Recurrent models limit parallelization on long sequences.",
                ),
            ]
        }

        pack = summarize_slide_analysis_pack(grouped_hits)
        refined = refine_slide_analysis_pack(
            pack,
            refine_func=lambda family_key, hits: [
                hit for hit in hits if family_key == "paper_motivation" and hit.chunk_id == "c-problem"
            ],
        )

        self.assertEqual(
            [hit.chunk_id for hit in refined.query_family_hits["paper_motivation"]],
            ["c-problem"],
        )


if __name__ == "__main__":
    unittest.main()
