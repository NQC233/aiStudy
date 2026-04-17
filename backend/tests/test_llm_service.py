import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.llm_service import (
    _extract_json_object,
    _call_slides_json_model,
    describe_visual_asset,
    generate_slide_html_page,
    generate_slide_scene_spec,
    generate_slides_presentation_plan,
)
from app.core.config import Settings


class LlmServiceTests(unittest.TestCase):
    def test_call_slides_json_model_uses_slides_specific_timeout(self) -> None:
        import json
        from unittest.mock import MagicMock, patch

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"page_count": 8, "pages": []}, ensure_ascii=False)
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with patch("app.services.llm_service.urlopen", return_value=fake_response) as mocked_urlopen:
            _call_slides_json_model(
                task_name="analysis",
                system_prompt="test",
                user_payload={"analysis_pack": {}, "visual_asset_catalog": []},
            )

        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], Settings().dashscope_slides_timeout_sec)

    def test_call_slides_json_model_uses_planner_timeout_for_analysis_task(self) -> None:
        import json
        from unittest.mock import MagicMock, patch

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"page_count": 8, "pages": []}, ensure_ascii=False)
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with patch("app.services.llm_service.urlopen", return_value=fake_response) as mocked_urlopen:
            _call_slides_json_model(
                task_name="analysis",
                system_prompt="test",
                user_payload={"analysis_pack": {}, "visual_asset_catalog": []},
            )

        self.assertEqual(
            mocked_urlopen.call_args.kwargs["timeout"],
            Settings().dashscope_slides_planner_timeout_sec,
        )

    def test_call_slides_json_model_uses_scene_timeout_for_scene_task(self) -> None:
        import json
        from unittest.mock import MagicMock, patch

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"title": "方法页", "content_blocks": []}, ensure_ascii=False)
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with patch("app.services.llm_service.urlopen", return_value=fake_response) as mocked_urlopen:
            _call_slides_json_model(
                task_name="scene",
                system_prompt="test",
                user_payload={"page": {}, "analysis_pack": {}, "visual_asset_catalog": []},
            )

        self.assertEqual(
            mocked_urlopen.call_args.kwargs["timeout"],
            Settings().dashscope_slides_scene_timeout_sec,
        )

    def test_call_slides_json_model_uses_html_timeout_for_html_task(self) -> None:
        import json
        from unittest.mock import MagicMock, patch

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"html": "<section></section>", "css": "", "render_meta": {}}, ensure_ascii=False)
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with patch("app.services.llm_service.urlopen", return_value=fake_response) as mocked_urlopen:
            _call_slides_json_model(
                task_name="html",
                system_prompt="test",
                user_payload={"scene_spec": {}},
            )

        self.assertEqual(
            mocked_urlopen.call_args.kwargs["timeout"],
            Settings().dashscope_slides_html_timeout_sec,
        )

    def test_settings_use_dashscope_lowercase_model_names_for_slides(self) -> None:
        settings = Settings()

        self.assertEqual(settings.dashscope_slides_analysis_model_name, "qwen3.6-plus")
        self.assertEqual(settings.dashscope_slides_vision_model_name, "qwen3.6-plus")
        self.assertEqual(settings.dashscope_slides_html_model_name, "qwen3.6-plus")
        self.assertEqual(settings.dashscope_slides_timeout_sec, 240)
        self.assertEqual(settings.dashscope_slides_planner_timeout_sec, 240)
        self.assertEqual(settings.dashscope_slides_scene_timeout_sec, 480)
        self.assertEqual(settings.dashscope_slides_html_timeout_sec, 480)
        self.assertEqual(settings.dashscope_image_model_name, "qwen-image-2.0-pro")

    def test_extract_json_object_tolerates_invalid_backslash_sequences(self) -> None:
        raw = (
            "{"
            '"title":"关键机制解析",'
            '"goal":"讲解关键机制",'
            '"script":"公式 $s_B(x)=\\mathsf{Linear}_N(x)$。",'
            '"evidence":"证据[1]"'
            "}"
        )

        payload = _extract_json_object(raw)

        self.assertEqual(payload["title"], "关键机制解析")
        self.assertIn("\\mathsf", payload["script"])

    def test_describe_visual_asset_returns_normalized_fields_from_injected_caller(self) -> None:
        asset = {
            "asset_id": "img-001",
            "asset_type": "image",
            "caption_text": "Figure 1: Transformer architecture.",
            "surrounding_context": "The encoder and decoder are both composed of stacked self-attention layers.",
            "public_url": "https://example.com/fig1.png",
        }

        described = describe_visual_asset(
            asset,
            model_caller=lambda prompt, asset_payload: {
                "vision_summary": asset_payload["caption_text"],
                "what_this_asset_shows": "Encoder-decoder stack overview",
                "why_it_matters": "Explains the core architecture",
                "best_scene_role": "method",
                "recommended_usage": "method_overview",
                "reuse_priority": "high",
            },
        )

        self.assertEqual(described["vision_summary"], "Figure 1: Transformer architecture.")
        self.assertEqual(described["recommended_usage"], "method_overview")
        self.assertEqual(described["reuse_priority"], "high")

    def test_generate_slides_presentation_plan_normalizes_model_output(self) -> None:
        plan = generate_slides_presentation_plan(
            {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            [{"asset_id": "fig-1", "recommended_usage": "method_overview"}],
            model_caller=lambda _prompt, _payload: {
                "page_count": 2,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "cover",
                        "narrative_goal": "Explain why Transformer matters.",
                        "content_focus": "paper_motivation",
                        "visual_strategy": "text_plus_original_figure",
                        "candidate_assets": ["fig-1"],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
        )

        self.assertEqual(plan["page_count"], 2)
        self.assertEqual(plan["pages"][0]["candidate_assets"], ["fig-1"])

    def test_generate_slides_presentation_plan_prompt_requires_chinese_output(self) -> None:
        captured_prompt: dict[str, str] = {}

        generate_slides_presentation_plan(
            {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            [],
            model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
                "page_count": 1,
                "pages": [],
            },
        )

        self.assertIn("中文", captured_prompt["prompt"])
        self.assertIn("导演", captured_prompt["prompt"])
        self.assertIn("严禁", captured_prompt["prompt"])
        self.assertIn("至少 8 页", captured_prompt["prompt"])
        self.assertIn("示例", captured_prompt["prompt"])

    def test_generate_slide_scene_spec_normalizes_model_output(self) -> None:
        scene = generate_slide_scene_spec(
            {
                "page_id": "page-1",
                "scene_role": "method",
                "narrative_goal": "Explain the architecture.",
                "content_focus": "method_overview",
                "visual_strategy": "text_plus_original_figure",
                "candidate_assets": ["fig-1"],
                "animation_intent": "stagger_reveal",
            },
            {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            [{"asset_id": "fig-1", "vision_summary": "Architecture figure."}],
            model_caller=lambda _prompt, _payload: {
                "title": "Transformer Architecture",
                "summary_line": "Self-attention replaces recurrence.",
                "layout_strategy": "hero-visual-right",
                "content_blocks": [{"type": "bullets", "items": ["Encoder", "Decoder"]}],
                "citations": [{"page_no": 3, "block_ids": ["b3"]}],
                "asset_bindings": [{"asset_id": "fig-1"}],
                "animation_plan": {"type": "stagger_reveal"},
                "speaker_note_seed": "Explain the encoder-decoder split.",
            },
        )

        self.assertEqual(scene["page_id"], "page-1")
        self.assertEqual(scene["asset_bindings"][0]["asset_id"], "fig-1")

    def test_generate_slide_scene_spec_prompt_requires_non_empty_chinese_content_blocks(self) -> None:
        captured_prompt: dict[str, str] = {}

        generate_slide_scene_spec(
            {
                "page_id": "page-1",
                "scene_role": "method",
                "narrative_goal": "Explain the architecture.",
                "content_focus": "method_overview",
                "visual_strategy": "text_plus_original_figure",
                "candidate_assets": ["fig-1"],
                "animation_intent": "stagger_reveal",
            },
            {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            [{"asset_id": "fig-1", "vision_summary": "Architecture figure."}],
            model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
                "title": "Transformer Architecture",
                "summary_line": "Self-attention replaces recurrence.",
                "layout_strategy": "hero-visual-right",
                "content_blocks": [{"type": "bullets", "items": ["Encoder", "Decoder"]}],
                "citations": [{"page_no": 3, "block_ids": ["b3"]}],
                "asset_bindings": [{"asset_id": "fig-1"}],
                "animation_plan": {"type": "stagger_reveal"},
                "speaker_note_seed": "Explain the encoder-decoder split.",
            },
        )

        self.assertIn("中文", captured_prompt["prompt"])
        self.assertIn("不能为空", captured_prompt["prompt"])
        self.assertIn("content_blocks", captured_prompt["prompt"])
        self.assertIn("逐页", captured_prompt["prompt"])
        self.assertIn("示例", captured_prompt["prompt"])
        self.assertIn("citations", captured_prompt["prompt"])

    def test_generate_slide_html_page_prompt_requires_chinese_not_title_paragraph_fallback(self) -> None:
        captured_prompt: dict[str, str] = {}

        generate_slide_html_page(
            {
                "page_id": "page-1",
                "title": "Transformer Architecture",
                "summary_line": "Self-attention replaces recurrence.",
                "layout_strategy": "hero-visual-right",
                "content_blocks": [{"type": "bullets", "items": ["Encoder", "Decoder"]}],
                "asset_bindings": [{"asset_id": "fig-1"}],
            },
            model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
                "html": "<section><h1>Transformer Architecture</h1></section>",
                "css": ".slide{color:#111;}",
                "render_meta": {"mode": "llm"},
            },
        )

        self.assertIn("中文", captured_prompt["prompt"])
        self.assertIn("title+paragraph", captured_prompt["prompt"])
        self.assertIn("16:9", captured_prompt["prompt"])
        self.assertIn("单页", captured_prompt["prompt"])
        self.assertIn("示例", captured_prompt["prompt"])

    def test_generate_slide_html_page_normalizes_model_output(self) -> None:
        rendered = generate_slide_html_page(
            {
                "page_id": "page-1",
                "title": "Transformer Architecture",
                "summary_line": "Self-attention replaces recurrence.",
                "layout_strategy": "hero-visual-right",
                "asset_bindings": [{"asset_id": "fig-1"}],
            },
            model_caller=lambda _prompt, _payload: {
                "html": "<section><h1>Transformer Architecture</h1></section>",
                "css": ".slide{color:#111;}",
                "render_meta": {"mode": "llm"},
            },
        )

        self.assertEqual(rendered["page_id"], "page-1")
        self.assertIn("Transformer Architecture", rendered["html"])
        self.assertEqual(rendered["render_meta"]["mode"], "llm")


if __name__ == "__main__":
    unittest.main()
