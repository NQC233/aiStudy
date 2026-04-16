import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


if __name__ == "__main__":
    unittest.main()
