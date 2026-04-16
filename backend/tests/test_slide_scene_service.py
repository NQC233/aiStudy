import sys
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


if __name__ == "__main__":
    unittest.main()
