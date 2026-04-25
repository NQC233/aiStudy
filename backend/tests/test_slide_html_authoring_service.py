import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_html_authoring_service import render_slide_pages
from app.services.slide_html_authoring_service import render_slide_pages_batch
from app.services.slide_html_authoring_service import render_slide_page
from app.services.slide_html_authoring_service import build_slide_validation_result
from app.services.slide_html_authoring_service import validate_rendered_slide_page
from app.services.slide_runtime_bundle_service import build_runtime_bundle


class SlideHtmlAuthoringServiceTestCase(unittest.TestCase):
    def test_render_slide_pages_batch_returns_page_level_pages_and_deck_meta(self) -> None:
        scene_specs = [
            {"page_id": "page-1", "title": "问题背景", "summary_line": "A"},
            {"page_id": "page-2", "title": "方法概览", "summary_line": "B"},
        ]

        result = render_slide_pages_batch(
            scene_specs,
            deck_style_guide={"theme_name": "paper-academic"},
            batch_html_writer=lambda scene_specs, **_kwargs: {
                "deck_meta": {"typography": {"title_scale": 42}},
                "pages": [
                    {
                        "page_id": scene_specs[0]["page_id"],
                        "html": "<section>问题背景</section>",
                        "css": ".page{}",
                        "render_meta": {},
                    },
                    {
                        "page_id": scene_specs[1]["page_id"],
                        "html": "<section>方法概览</section>",
                        "css": ".page{}",
                        "render_meta": {},
                    },
                ],
            },
        )

        self.assertEqual(result["deck_meta"]["typography"]["title_scale"], 42)
        self.assertEqual([page["page_id"] for page in result["pages"]], ["page-1", "page-2"])

    def test_render_slide_pages_batch_chunks_large_deck_and_reuses_first_chunk_deck_meta(self) -> None:
        seen_inputs: list[dict[str, object]] = []
        scene_specs = [
            {"page_id": "page-1", "title": "1", "summary_line": "1"},
            {"page_id": "page-2", "title": "2", "summary_line": "2"},
            {"page_id": "page-3", "title": "3", "summary_line": "3"},
        ]

        def fake_batch_writer(scene_specs, deck_meta=None, **_kwargs):
            seen_inputs.append(
                {"page_ids": [item["page_id"] for item in scene_specs], "deck_meta": deck_meta or {}}
            )
            return {
                "deck_meta": deck_meta or {"typography": {"title_scale": 42}},
                "pages": [
                    {
                        "page_id": item["page_id"],
                        "html": f"<section>{item['title']}</section>",
                        "css": ".page{}",
                        "render_meta": {},
                    }
                    for item in scene_specs
                ],
            }

        result = render_slide_pages_batch(
            scene_specs,
            deck_style_guide={"theme_name": "paper-academic"},
            batch_html_writer=fake_batch_writer,
            max_batch_pages=2,
            chunk_size=2,
        )

        self.assertEqual(seen_inputs[0]["page_ids"], ["page-1", "page-2"])
        self.assertEqual(seen_inputs[1]["page_ids"], ["page-3"])
        self.assertEqual(seen_inputs[1]["deck_meta"], {"typography": {"title_scale": 42}})
        self.assertEqual(len(result["pages"]), 3)

    def test_render_slide_pages_batch_falls_back_to_page_renderer_when_batch_shape_is_invalid(self) -> None:
        scene_specs = [
            {"page_id": "page-1", "title": "问题背景", "summary_line": "A"},
            {"page_id": "page-2", "title": "方法概览", "summary_line": "B"},
        ]

        result = render_slide_pages_batch(
            scene_specs,
            deck_style_guide={"theme_name": "paper-academic"},
            batch_html_writer=lambda _scene_specs, **_kwargs: {
                "deck_meta": {"typography": {"title_scale": 42}},
                "pages": [
                    {"page_id": "page-1", "title": "问题背景", "layout": "hero", "elements": []},
                    {"page_id": "page-2", "title": "方法概览", "layout": "hero", "elements": []},
                ],
            },
            page_html_writer=lambda scene, deck_style_guide=None: {
                "html": f"<section>{scene['title']}-{deck_style_guide['theme_name']}</section>",
                "css": ".page{}",
            },
        )

        self.assertEqual([page["page_id"] for page in result["pages"]], ["page-1", "page-2"])
        self.assertIn("问题背景-paper-academic", result["pages"][0]["html"])
        self.assertEqual([item["status"] for item in result["html_meta"]], ["success", "success"])

        result = validate_rendered_slide_page(
            page_number=2,
            html="<div class='slide-page'><h1>Title</h1><p>Body</p></div>",
            css=".slide-page{width:100%;min-height:100vh;overflow:visible;}",
            canvas_width=1600,
            canvas_height=900,
            timeout_sec=8,
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["blocking"])
        self.assertEqual(result["reason"], "canvas_contract_missing")

    def test_validate_rendered_slide_page_passes_with_fixed_canvas_contract_in_html_inline_styles(self) -> None:
        result = validate_rendered_slide_page(
            page_number=5,
            html=(
                "<html><body style='margin:0;padding:0;width:1600px;height:900px;overflow:hidden'>"
                "<div id='canvas' style='width:1600px;height:900px;overflow:hidden;position:relative'>"
                "<section class='content'>内容</section>"
                "</div></body></html>"
            ),
            css="#canvas { background: #f8f9fa; } .content { max-height: 760px; overflow: hidden; }",
            canvas_width=1600,
            canvas_height=900,
            timeout_sec=8,
        )

        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["blocking"])
        self.assertIsNone(result["reason"])

    def test_validate_rendered_slide_page_passes_with_explicit_fixed_canvas_contract(self) -> None:
        result = validate_rendered_slide_page(
            page_number=4,
            html=(
                "<html><body><div class='slide-canvas'><section class='content'>内容</section></div></body></html>"
            ),
            css=(
                "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ".content { max-height: 760px; overflow: hidden; }"
            ),
            canvas_width=1600,
            canvas_height=900,
            timeout_sec=8,
        )

        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["blocking"])
        self.assertIsNone(result["reason"])

    def test_validate_rendered_slide_page_reports_failure_for_obvious_overflow(self) -> None:
        result = validate_rendered_slide_page(
            page_number=3,
            html="<html><body><div style='height:2000px'>overflow</div></body></html>",
            css=(
                "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ".overflow-block { height: 2000px; overflow: visible; }"
            ),
            canvas_width=1600,
            canvas_height=900,
            timeout_sec=8,
        )

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["blocking"])
        self.assertEqual(result["reason"], "overflow_detected")

    def test_build_slide_validation_result_reports_skipped_when_disabled(self) -> None:
        result = build_slide_validation_result(
            enabled=False,
            page_number=1,
            html="<html></html>",
            css=".page{}",
            canvas_width=1600,
            canvas_height=900,
            timeout_sec=8,
        )

        self.assertEqual(
            result,
            {
                "status": "skipped",
                "blocking": False,
                "reason": "validation_disabled",
            },
        )

    def test_render_slide_page_returns_page_level_html_payload(self) -> None:
        scene_spec = {
            "page_id": "page-1",
            "title": "Transformer Architecture",
            "summary_line": "Self-attention replaces recurrence.",
        }

        rendered = render_slide_page(
            scene_spec,
            html_writer=lambda scene: {
                "html": f"<section>{scene['title']}</section>",
                "css": ".page{}",
            },
        )

        self.assertEqual(rendered["page_id"], "page-1")
        self.assertIn("Transformer Architecture", rendered["html"])

    def test_render_slide_page_records_trimmed_content_when_budget_exceeded(self) -> None:
        scene_spec = {
            "page_id": "page-1",
            "title": "方法结构",
            "summary_line": "介绍整体架构。",
            "layout_strategy": "hero-text",
            "content_blocks": [
                {"type": "bullets", "items": ["A", "B", "C", "D", "E", "F"]},
            ],
            "page_budget": {
                "max_blocks": 3,
                "content_budget": {"bullet_max_items": 4},
                "overflow_strategy": {"mode": "trim_then_split"},
                "continuation_policy": {"enabled": True, "max_extra_pages": 3},
            },
        }

        rendered = render_slide_page(
            scene_spec,
            html_writer=lambda scene, deck_style_guide=None: {
                "html": "<section>ok</section>",
                "css": ".page{}",
            },
        )

        repair_meta = rendered["render_meta"]["repair_hints"]
        self.assertEqual(repair_meta["status"], "trimmed")
        self.assertEqual(repair_meta["trimmed_block_count"], 1)
        self.assertEqual(repair_meta["overflow_residue"][0]["type"], "bullets")

    def test_render_slide_page_records_clean_budget_when_content_fits(self) -> None:
        scene_spec = {
            "page_id": "page-1",
            "title": "方法结构",
            "summary_line": "介绍整体架构。",
            "layout_strategy": "hero-text",
            "content_blocks": [
                {"type": "bullets", "items": ["A", "B", "C"]},
            ],
            "page_budget": {
                "max_blocks": 3,
                "content_budget": {"bullet_max_items": 4},
                "overflow_strategy": {"mode": "trim_then_split"},
                "continuation_policy": {"enabled": True, "max_extra_pages": 3},
            },
        }

        rendered = render_slide_page(
            scene_spec,
            html_writer=lambda scene, deck_style_guide=None: {
                "html": "<section>ok</section>",
                "css": ".page{}",
            },
        )

        repair_meta = rendered["render_meta"]["repair_hints"]
        self.assertEqual(repair_meta["status"], "clean")
        self.assertEqual(repair_meta["trimmed_block_count"], 0)
        self.assertEqual(repair_meta["overflow_residue"], [])

    def test_build_runtime_bundle_wraps_rendered_pages(self) -> None:
        bundle = build_runtime_bundle(
            [
                {
                    "page_id": "page-1",
                    "html": "<section>One</section>",
                    "css": ".one{}",
                    "asset_refs": [],
                    "render_meta": {},
                }
            ]
        )

        self.assertEqual(bundle["page_count"], 1)
        self.assertEqual(bundle["playable_page_count"], 1)
        self.assertEqual(bundle["failed_page_numbers"], [])
        self.assertEqual(bundle["validation_summary"]["status"], "ready")
        self.assertEqual(bundle["pages"][0]["page_id"], "page-1")

    def test_build_runtime_bundle_marks_mixed_pages_as_partial_ready(self) -> None:
        bundle = build_runtime_bundle(
            [
                {
                    "page_id": "page-1",
                    "html": "<section>One</section>",
                    "css": ".one{}",
                    "asset_refs": [],
                    "render_meta": {},
                },
                {
                    "page_id": "page-2",
                    "html": "<section>Two</section>",
                    "css": ".two{}",
                    "asset_refs": [],
                    "render_meta": {
                        "validation": {
                            "status": "failed",
                            "reason": "overflow detected",
                        }
                    },
                },
            ]
        )

        self.assertEqual(bundle["page_count"], 2)
        self.assertEqual(bundle["playable_page_count"], 1)
        self.assertEqual(bundle["failed_page_numbers"], [2])
        self.assertEqual(bundle["validation_summary"]["status"], "partial_ready")

    def test_render_slide_pages_preserves_scene_order_under_parallel_execution(self) -> None:
        scene_specs = [
            {"page_id": "page-1", "title": "第一页", "summary_line": "A"},
            {"page_id": "page-2", "title": "第二页", "summary_line": "B"},
            {"page_id": "page-3", "title": "第三页", "summary_line": "C"},
        ]

        def delayed_html_writer(scene, deck_style_guide=None):
            if scene["page_id"] == "page-1":
                time.sleep(0.08)
            if scene["page_id"] == "page-2":
                time.sleep(0.01)
            return {
                "html": f"<section>{scene['title']}-{deck_style_guide['theme_name']}</section>",
                "css": ".page{}",
            }

        rendered_pages, html_meta = render_slide_pages(
            scene_specs,
            html_writer=delayed_html_writer,
            parallelism=3,
            deck_style_guide={"theme_name": "paper-dark"},
        )

        self.assertEqual([page["page_id"] for page in rendered_pages], ["page-1", "page-2", "page-3"])
        self.assertEqual([item["status"] for item in html_meta], ["success", "success", "success"])

    def test_render_slide_pages_passes_same_deck_style_guide_to_each_page(self) -> None:
        seen_themes: list[str] = []
        scene_specs = [{"page_id": "page-1", "title": "第一页", "summary_line": "A"}]

        rendered_pages, _html_meta = render_slide_pages(
            scene_specs,
            html_writer=lambda scene, deck_style_guide=None: seen_themes.append(deck_style_guide["theme_name"]) or {
                "html": f"<section>{scene['title']}</section>",
                "css": ".page{}",
            },
            deck_style_guide={"theme_name": "lab-blue", "language": "zh-CN"},
        )

        self.assertEqual(seen_themes, ["lab-blue"])
        self.assertEqual(rendered_pages[0]["page_id"], "page-1")

    def test_render_slide_pages_isolates_failed_pages_when_parallel(self) -> None:
        scene_specs = [
            {"page_id": "page-1", "title": "第一页", "summary_line": "A", "layout_strategy": "hero"},
            {"page_id": "page-2", "title": "第二页", "summary_line": "B", "layout_strategy": "hero"},
        ]

        rendered_pages, html_meta = render_slide_pages(
            scene_specs,
            html_writer=lambda scene, deck_style_guide=None: (
                (_ for _ in ()).throw(RuntimeError("html page failed"))
                if scene["page_id"] == "page-2"
                else {"html": f"<section>{scene['title']}</section>", "css": ".page{}"}
            ),
            parallelism=2,
            deck_style_guide={"theme_name": "paper-dark"},
        )

        self.assertEqual(html_meta[0]["status"], "success")
        self.assertEqual(html_meta[1]["status"], "fallback")
        self.assertIn("第二页", rendered_pages[1]["html"])


if __name__ == "__main__":
    unittest.main()
