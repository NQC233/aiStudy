import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.reader import ParsedDocumentPayload
from app.services.slide_lesson_plan_service import (
    _is_low_signal_quote,
    build_lesson_plan_summary,
    build_stage_lesson_plan,
    can_enqueue_lesson_plan_rebuild,
    run_asset_lesson_plan_pipeline,
    is_slides_processing_stale,
)


class SlideLessonPlanServiceTests(unittest.TestCase):
    def test_low_signal_quote_filters_google_authorization_clause(self) -> None:
        self.assertTrue(
            _is_low_signal_quote(
                "Provided proper attribution is provided, Google hereby grants permission to reproduce the..."
            )
        )
        self.assertFalse(_is_low_signal_quote("Transformer 在多个翻译任务上超过 RNN 基线。"))

    def test_build_stage_lesson_plan_covers_five_story_stages(self) -> None:
        payload = ParsedDocumentPayload.model_validate(
            {
                "schema_version": "v1",
                "asset_id": "asset-1",
                "parse_id": "parse-1",
                "document": {"title": "Paper"},
                "pages": [
                    {
                        "page_id": "p1",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "blocks": ["b1", "b2"],
                    },
                    {
                        "page_id": "p2",
                        "page_no": 2,
                        "source_page_idx": 1,
                        "blocks": ["b3", "b4"],
                    },
                    {
                        "page_id": "p3",
                        "page_no": 3,
                        "source_page_idx": 2,
                        "blocks": ["b5"],
                    },
                ],
                "sections": [
                    {
                        "section_id": "s1",
                        "title": "Introduction",
                        "level": 1,
                        "page_start": 1,
                        "page_end": 1,
                        "block_ids": ["b1"],
                    },
                    {
                        "section_id": "s2",
                        "title": "Method",
                        "level": 1,
                        "page_start": 1,
                        "page_end": 2,
                        "block_ids": ["b2", "b3"],
                    },
                    {
                        "section_id": "s3",
                        "title": "Experiments",
                        "level": 1,
                        "page_start": 2,
                        "page_end": 3,
                        "block_ids": ["b4", "b5"],
                    },
                ],
                "blocks": [
                    {
                        "block_id": "b1",
                        "type": "paragraph",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "order": 1,
                        "section_id": "s1",
                        "text": "Background problem and motivation.",
                        "paragraph_no": 1,
                    },
                    {
                        "block_id": "b2",
                        "type": "paragraph",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "order": 2,
                        "section_id": "s2",
                        "text": "Method overview and key framework.",
                        "paragraph_no": 2,
                    },
                    {
                        "block_id": "b3",
                        "type": "paragraph",
                        "page_no": 2,
                        "source_page_idx": 1,
                        "order": 3,
                        "section_id": "s2",
                        "text": "Mechanism implementation details.",
                        "paragraph_no": 3,
                    },
                    {
                        "block_id": "b4",
                        "type": "paragraph",
                        "page_no": 2,
                        "source_page_idx": 1,
                        "order": 4,
                        "section_id": "s3",
                        "text": "Experiment results and benchmarks.",
                        "paragraph_no": 4,
                    },
                    {
                        "block_id": "b5",
                        "type": "paragraph",
                        "page_no": 3,
                        "source_page_idx": 2,
                        "order": 5,
                        "section_id": "s3",
                        "text": "Conclusion and future work.",
                        "paragraph_no": 5,
                    },
                ],
            }
        )

        lesson_plan = build_stage_lesson_plan(payload, story_evidence={})
        self.assertEqual(
            [stage.stage for stage in lesson_plan.stages],
            ["problem", "method", "mechanism", "experiment", "conclusion"],
        )
        self.assertTrue(
            all(len(stage.evidence_anchors) >= 1 for stage in lesson_plan.stages)
        )
        self.assertTrue(
            all("Spec 11B/11C" not in stage.script for stage in lesson_plan.stages)
        )
        self.assertTrue(
            all(not stage.goal.startswith("完成“") for stage in lesson_plan.stages)
        )

    def test_lesson_plan_summary_contains_anchor_counts(self) -> None:
        payload = ParsedDocumentPayload.model_validate(
            {
                "schema_version": "v1",
                "asset_id": "asset-2",
                "parse_id": "parse-2",
                "document": {"title": "Paper"},
                "pages": [
                    {
                        "page_id": "p1",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "blocks": ["b1"],
                    }
                ],
                "sections": [
                    {
                        "section_id": "s1",
                        "title": "Introduction",
                        "level": 1,
                        "page_start": 1,
                        "page_end": 1,
                        "block_ids": ["b1"],
                    }
                ],
                "blocks": [
                    {
                        "block_id": "b1",
                        "type": "paragraph",
                        "page_no": 1,
                        "source_page_idx": 0,
                        "order": 1,
                        "section_id": "s1",
                        "text": "Problem statement.",
                    }
                ],
            }
        )
        lesson_plan = build_stage_lesson_plan(payload, story_evidence={})
        summary = build_lesson_plan_summary(lesson_plan)
        self.assertEqual(len(summary), 5)
        self.assertTrue(all(item.anchor_count >= 1 for item in summary))

    def test_rebuild_enqueue_status_flow_guard(self) -> None:
        self.assertEqual(
            can_enqueue_lesson_plan_rebuild("ready", "not_generated"), (True, "ok")
        )
        self.assertEqual(
            can_enqueue_lesson_plan_rebuild("processing", "not_generated"),
            (False, "parse_not_ready"),
        )
        self.assertEqual(
            can_enqueue_lesson_plan_rebuild("ready", "processing"),
            (False, "already_processing"),
        )

    def test_processing_stale_detection_respects_timeout(self) -> None:
        now = datetime.now(timezone.utc)
        stale_time = now - timedelta(seconds=301)
        fresh_time = now - timedelta(seconds=45)

        self.assertTrue(
            is_slides_processing_stale(
                updated_at=stale_time,
                now=now,
                stale_after_seconds=300,
            )
        )
        self.assertFalse(
            is_slides_processing_stale(
                updated_at=fresh_time,
                now=now,
                stale_after_seconds=300,
            )
        )
        self.assertFalse(
            is_slides_processing_stale(
                updated_at=None,
                now=now,
                stale_after_seconds=300,
            )
        )

    def test_lesson_plan_success_keeps_slides_processing_until_dsl_finishes(
        self,
    ) -> None:
        asset = SimpleNamespace(
            id="asset-1", parse_status="ready", slides_status="processing"
        )
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            active_run_token=None,
            lesson_plan=None,
            version=0,
            error_meta={},
        )

        class ScalarResult:
            def __init__(self, obj):
                self.obj = obj

            def one(self):
                return self.obj

        class FakeDb:
            def scalars(self, _statement):
                return ScalarResult(presentation)

            def commit(self):
                return None

        class FakeLessonPlan:
            def model_dump(self, mode="json"):
                return {"stages": []}

        fake_db = FakeDb()

        with (
            patch("app.services.slide_lesson_plan_service._bootstrap_presentation"),
            patch(
                "app.services.slide_lesson_plan_service._load_parsed_payload",
                return_value=object(),
            ),
            patch(
                "app.services.slide_lesson_plan_service._load_story_evidence",
                return_value={},
            ),
            patch(
                "app.services.slide_lesson_plan_service.build_stage_lesson_plan",
                return_value=FakeLessonPlan(),
            ),
            patch(
                "app.services.slide_lesson_plan_service._require_asset",
                return_value=asset,
            ),
            patch(
                "app.services.slide_lesson_plan_service.uuid4",
                return_value=SimpleNamespace(hex="run-token"),
            ),
        ):
            result = run_asset_lesson_plan_pipeline(fake_db, asset_id="asset-1")

        self.assertEqual(result["status"], "ready")
        self.assertEqual(presentation.status, "ready")
        self.assertEqual(asset.slides_status, "processing")


if __name__ == "__main__":
    unittest.main()
