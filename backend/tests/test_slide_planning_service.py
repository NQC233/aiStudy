import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_planning_service import build_presentation_plan


class SlidePlanningServiceTestCase(unittest.TestCase):
    def test_build_presentation_plan_creates_roles_and_visual_strategy(self) -> None:
        analysis_pack = {
            "core_claims": [
                "Transformer removes recurrence and relies entirely on attention."
            ],
            "main_results": [
                "Transformer improves BLEU on WMT14 En-De and En-Fr."
            ],
        }
        visual_asset_catalog = [
            {"asset_id": "fig-1", "recommended_usage": "method_overview"}
        ]

        plan = build_presentation_plan(
            analysis_pack,
            visual_asset_catalog,
            plan_writer=lambda *_args, **_kwargs: {
                "page_count": 8,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "cover",
                        "narrative_goal": "Introduce the paper contribution.",
                        "content_focus": "core_claim",
                        "visual_strategy": "text_plus_original_figure",
                        "candidate_assets": ["fig-1"],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
        )

        self.assertEqual(plan["page_count"], 8)
        self.assertEqual(plan["pages"][0]["scene_role"], "cover")

    def test_build_presentation_plan_rejects_single_page_overview_for_rich_analysis(self) -> None:
        analysis_pack = {
            "problem_statements": ["Recurrence slows training on long sequences."],
            "method_components": ["Self-attention encoder-decoder.", "Multi-head attention."],
            "main_results": ["Better BLEU with much less training cost."],
            "ablations": ["Removing multi-head attention hurts BLEU."],
            "limitations": ["Quadratic complexity for long sequences."],
        }
        visual_asset_catalog = [
            {"asset_id": "fig-1", "recommended_usage": "method_overview"},
            {"asset_id": "tbl-1", "recommended_usage": "results_comparison"},
        ]

        plan = build_presentation_plan(
            analysis_pack,
            visual_asset_catalog,
            plan_writer=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "overview",
                        "narrative_goal": "Paper Overview",
                        "content_focus": "core_claims",
                        "visual_strategy": "text_plus_original_figure",
                        "candidate_assets": ["fig-1"],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
        )

        self.assertGreaterEqual(plan["page_count"], 4)
        self.assertEqual(plan["pages"][0]["scene_role"], "problem")

    def test_build_presentation_plan_uses_multi_page_fallback_for_rich_analysis_when_writer_fails(self) -> None:
        analysis_pack = {
            "problem_statements": ["Recurrence slows training on long sequences."],
            "method_components": ["Self-attention encoder-decoder.", "Multi-head attention."],
            "method_steps": ["Encode tokens with positional information.", "Apply stacked attention blocks."],
            "main_results": ["Better BLEU with much less training cost."],
            "ablations": ["Removing multi-head attention hurts BLEU."],
            "limitations": ["Quadratic complexity for long sequences."],
        }
        visual_asset_catalog = [
            {"asset_id": "fig-1", "recommended_usage": "method_overview"},
            {"asset_id": "tbl-1", "recommended_usage": "results_comparison"},
        ]

        plan = build_presentation_plan(
            analysis_pack,
            visual_asset_catalog,
            plan_writer=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("planner timeout")),
        )

        self.assertGreaterEqual(plan["page_count"], 4)
        self.assertGreaterEqual(len(plan["pages"]), 4)
        self.assertEqual(plan["pages"][0]["scene_role"], "problem")
        self.assertEqual(plan["pages"][1]["scene_role"], "method")
        self.assertEqual(plan["pages"][2]["scene_role"], "results")


if __name__ == "__main__":
    unittest.main()
