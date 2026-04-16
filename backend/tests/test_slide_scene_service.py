import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_scene_service import build_scene_specs


class SlideSceneServiceTestCase(unittest.TestCase):
    def test_build_scene_specs_creates_page_level_scene_units(self) -> None:
        presentation_plan = {
            "page_count": 1,
            "pages": [
                {
                    "page_id": "page-1",
                    "scene_role": "method",
                    "narrative_goal": "Explain the architecture.",
                    "content_focus": "method_overview",
                    "visual_strategy": "text_plus_original_figure",
                    "candidate_assets": ["fig-1"],
                    "animation_intent": "stagger_reveal",
                }
            ],
        }

        scenes = build_scene_specs(
            presentation_plan,
            scene_writer=lambda page, *_args, **_kwargs: {
                "page_id": page["page_id"],
                "title": "Transformer Architecture",
                "summary_line": "Self-attention replaces recurrence.",
                "layout_strategy": "hero-visual-right",
                "content_blocks": [{"type": "bullets", "items": ["Encoder", "Decoder"]}],
                "citations": [{"page_no": 4, "block_ids": ["block-1"]}],
                "asset_bindings": [{"asset_id": "fig-1"}],
                "animation_plan": {"type": "stagger_reveal"},
                "speaker_note_seed": "Start from the encoder-decoder split.",
            },
        )

        self.assertEqual(scenes[0]["page_id"], "page-1")
        self.assertEqual(scenes[0]["layout_strategy"], "hero-visual-right")

    def test_build_scene_specs_default_path_passes_analysis_and_visual_context(self) -> None:
        presentation_plan = {
            "page_count": 1,
            "pages": [
                {
                    "page_id": "page-1",
                    "scene_role": "method",
                    "narrative_goal": "Explain the architecture.",
                }
            ],
        }
        analysis_pack = {
            "main_results": ["Better BLEU with less training cost."],
            "method_components": ["Self-attention encoder-decoder."],
        }
        visual_asset_catalog = [{"asset_id": "fig-1", "vision_summary": "Architecture figure."}]
        captured: dict[str, object] = {}

        scenes = build_scene_specs(
            presentation_plan,
            analysis_pack=analysis_pack,
            visual_asset_catalog=visual_asset_catalog,
            scene_generator=lambda page, seen_analysis_pack, seen_visual_asset_catalog: captured.update(
                {
                    "page": page,
                    "analysis_pack": seen_analysis_pack,
                    "visual_asset_catalog": seen_visual_asset_catalog,
                }
            ) or {
                "page_id": page["page_id"],
                "title": "Transformer Architecture",
                "summary_line": seen_analysis_pack["main_results"][0],
                "layout_strategy": "hero-visual-right",
                "content_blocks": [],
                "citations": [],
                "asset_bindings": [{"asset_id": seen_visual_asset_catalog[0]["asset_id"]}],
                "animation_plan": {"type": "soft_intro"},
                "speaker_note_seed": "Explain the encoder-decoder split.",
            },
        )

        self.assertEqual(captured["analysis_pack"]["main_results"][0], "Better BLEU with less training cost.")
        self.assertEqual(captured["visual_asset_catalog"][0]["asset_id"], "fig-1")
        self.assertEqual(scenes[0]["asset_bindings"][0]["asset_id"], "fig-1")

    def test_build_scene_specs_preserves_plan_order_under_parallel_execution(self) -> None:
        presentation_plan = {
            "page_count": 3,
            "pages": [
                {"page_id": "page-1", "scene_role": "cover", "narrative_goal": "第一页"},
                {"page_id": "page-2", "scene_role": "method", "narrative_goal": "第二页"},
                {"page_id": "page-3", "scene_role": "results", "narrative_goal": "第三页"},
            ],
            "deck_style_guide": {"theme_name": "paper-dark", "language": "zh-CN"},
        }

        def delayed_scene_generator(page, _analysis_pack, _visual_asset_catalog, deck_style_guide=None):
            if page["page_id"] == "page-1":
                time.sleep(0.08)
            if page["page_id"] == "page-2":
                time.sleep(0.01)
            return {
                "page_id": page["page_id"],
                "title": page["narrative_goal"],
                "summary_line": page["narrative_goal"],
                "layout_strategy": "hero-text",
                "content_blocks": [{"type": "bullets", "items": [page["page_id"]]}],
                "citations": [{"page_no": 1, "block_ids": [page["page_id"]]}],
                "asset_bindings": [],
                "animation_plan": {"type": "soft_intro"},
                "speaker_note_seed": deck_style_guide["theme_name"],
            }

        scenes = build_scene_specs(
            presentation_plan,
            scene_generator=delayed_scene_generator,
            parallelism=3,
        )

        self.assertEqual([scene["page_id"] for scene in scenes], ["page-1", "page-2", "page-3"])

    def test_build_scene_specs_passes_deck_style_guide_to_each_page(self) -> None:
        presentation_plan = {
            "page_count": 1,
            "pages": [
                {
                    "page_id": "page-1",
                    "scene_role": "method",
                    "narrative_goal": "解释架构",
                }
            ],
            "deck_style_guide": {
                "theme_name": "lab-blue",
                "language": "zh-CN",
                "layout_grammar": "headline-plus-evidence",
            },
        }
        captured: dict[str, object] = {}

        build_scene_specs(
            presentation_plan,
            scene_generator=lambda page, _analysis_pack, _visual_asset_catalog, deck_style_guide=None: captured.update(
                {"page": page, "deck_style_guide": deck_style_guide}
            ) or {
                "page_id": page["page_id"],
                "title": "解释架构",
                "summary_line": "解释架构",
                "layout_strategy": "hero-text",
                "content_blocks": [{"type": "bullets", "items": ["a"]}],
                "citations": [{"page_no": 1, "block_ids": ["b1"]}],
                "asset_bindings": [],
                "animation_plan": {"type": "soft_intro"},
                "speaker_note_seed": "lab-blue",
            },
        )

        self.assertEqual(captured["deck_style_guide"]["theme_name"], "lab-blue")
        self.assertEqual(captured["deck_style_guide"]["layout_grammar"], "headline-plus-evidence")

    def test_build_scene_specs_isolates_failed_pages_when_parallel(self) -> None:
        presentation_plan = {
            "page_count": 2,
            "pages": [
                {"page_id": "page-1", "scene_role": "cover", "narrative_goal": "第一页"},
                {"page_id": "page-2", "scene_role": "method", "narrative_goal": "第二页"},
            ],
        }

        def flaky_scene_generator(page, _analysis_pack, _visual_asset_catalog, deck_style_guide=None):
            if page["page_id"] == "page-2":
                raise RuntimeError("scene page failed")
            return {
                "page_id": page["page_id"],
                "title": page["narrative_goal"],
                "summary_line": page["narrative_goal"],
                "layout_strategy": "hero-text",
                "content_blocks": [{"type": "bullets", "items": [page["page_id"]]}],
                "citations": [{"page_no": 1, "block_ids": [page["page_id"]]}],
                "asset_bindings": [],
                "animation_plan": {"type": "soft_intro"},
                "speaker_note_seed": str(deck_style_guide or {}),
            }

        scenes = build_scene_specs(
            presentation_plan,
            scene_generator=flaky_scene_generator,
            parallelism=2,
        )

        self.assertEqual(scenes[0]["_debug"]["scene_source"], "generated")
        self.assertEqual(scenes[1]["_debug"]["scene_source"], "fallback")
        self.assertTrue(scenes[1]["_debug"]["is_empty_scene"])


if __name__ == "__main__":
    unittest.main()
