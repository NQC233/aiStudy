import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.slide_dsl import SlidesDslPayload
from app.services.slide_playback_service import (
    build_playback_plan_from_slides,
    build_tts_manifest_placeholders,
    resolve_tts_status,
)


def _slides_payload() -> SlidesDslPayload:
    return SlidesDslPayload.model_validate(
        {
            "asset_id": "asset-tts",
            "version": 1,
            "generated_at": "2026-04-06T00:00:00Z",
            "pages": [
                {
                    "slide_key": "slide:problem:1",
                    "stage": "problem",
                    "template_type": "problem_statement",
                    "animation_preset": "title_in",
                    "blocks": [
                        {"block_type": "title", "content": "问题背景"},
                        {
                            "block_type": "script",
                            "content": "我们先定义问题，再看方法。",
                        },
                    ],
                    "citations": [],
                },
                {
                    "slide_key": "slide:method:2",
                    "stage": "method",
                    "template_type": "method_overview",
                    "animation_preset": "bullet_stagger",
                    "blocks": [
                        {"block_type": "title", "content": "方法概览"},
                        {
                            "block_type": "script",
                            "content": "接着介绍核心模块以及训练策略。",
                        },
                    ],
                    "citations": [],
                },
            ],
        }
    )


class SlidePlaybackServiceTests(unittest.TestCase):
    def test_build_tts_manifest_placeholders_marks_pages_pending(self) -> None:
        payload = _slides_payload()

        manifest = build_tts_manifest_placeholders(payload)

        self.assertEqual(len(manifest.pages), 2)
        self.assertTrue(all(item.status == "pending" for item in manifest.pages))
        self.assertEqual(manifest.pages[0].slide_key, "slide:problem:1")

    def test_build_playback_plan_creates_page_and_block_timeline(self) -> None:
        payload = _slides_payload()

        plan = build_playback_plan_from_slides(payload)

        self.assertEqual(len(plan.pages), 2)
        self.assertGreater(plan.total_duration_ms, 0)
        self.assertEqual(plan.pages[0].cues[0].start_ms, 0)
        self.assertGreater(plan.pages[0].cues[0].end_ms, plan.pages[0].cues[0].start_ms)
        self.assertGreaterEqual(plan.pages[1].start_ms, plan.pages[0].end_ms)

    def test_resolve_tts_status_uses_manifest_page_statuses(self) -> None:
        self.assertEqual(resolve_tts_status([]), "not_generated")
        self.assertEqual(resolve_tts_status(["pending", "processing"]), "processing")
        self.assertEqual(resolve_tts_status(["ready", "ready"]), "ready")
        self.assertEqual(resolve_tts_status(["failed", "failed"]), "failed")
        self.assertEqual(resolve_tts_status(["ready", "failed"]), "partial")


if __name__ == "__main__":
    unittest.main()
