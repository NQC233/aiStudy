import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_html_authoring_service import render_slide_pages
from app.services.slide_html_authoring_service import render_slide_page
from app.services.slide_runtime_bundle_service import build_runtime_bundle


class SlideHtmlAuthoringServiceTestCase(unittest.TestCase):
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
        self.assertEqual(bundle["pages"][0]["page_id"], "page-1")

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
