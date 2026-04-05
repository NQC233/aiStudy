import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.slide_lesson_plan import AssetLessonPlanPayload
from app.services.slide_dsl_service import (
    build_slides_dsl,
    build_slides_dsl_with_strategy,
)
from app.services.slide_fix_service import repair_low_quality_pages
from app.services.slide_quality_service import (
    evaluate_slides_quality,
    validate_slides_must_pass,
)


def _lesson_plan_payload() -> AssetLessonPlanPayload:
    return AssetLessonPlanPayload.model_validate(
        {
            "asset_id": "asset-11b",
            "version": 2,
            "generated_at": "2026-04-01T00:00:00Z",
            "stages": [
                {
                    "stage": "problem",
                    "title": "问题背景",
                    "goal": "说明问题",
                    "script": "占位",
                    "evidence_anchors": [
                        {
                            "page_no": 1,
                            "block_ids": ["b1"],
                            "paragraph_ref": "1",
                            "quote": "问题描述",
                            "selector_payload": {
                                "selector_type": "block",
                                "block_id": "b1",
                            },
                        }
                    ],
                },
                {
                    "stage": "method",
                    "title": "方法概览",
                    "goal": "说明方法",
                    "script": "占位",
                    "evidence_anchors": [
                        {
                            "page_no": 2,
                            "block_ids": ["b2"],
                            "paragraph_ref": "2",
                            "quote": "方法描述",
                            "selector_payload": {
                                "selector_type": "block",
                                "block_id": "b2",
                            },
                        }
                    ],
                },
                {
                    "stage": "mechanism",
                    "title": "关键机制",
                    "goal": "说明机制",
                    "script": "占位",
                    "evidence_anchors": [
                        {
                            "page_no": 3,
                            "block_ids": ["b3"],
                            "paragraph_ref": "3",
                            "quote": "机制描述",
                            "selector_payload": {
                                "selector_type": "block",
                                "block_id": "b3",
                            },
                        }
                    ],
                },
                {
                    "stage": "experiment",
                    "title": "实验结果",
                    "goal": "说明实验",
                    "script": "占位",
                    "evidence_anchors": [
                        {
                            "page_no": 4,
                            "block_ids": ["b4"],
                            "paragraph_ref": "4",
                            "quote": "实验描述",
                            "selector_payload": {
                                "selector_type": "block",
                                "block_id": "b4",
                            },
                        }
                    ],
                },
                {
                    "stage": "conclusion",
                    "title": "结论与启发",
                    "goal": "总结结论",
                    "script": "占位",
                    "evidence_anchors": [
                        {
                            "page_no": 5,
                            "block_ids": ["b5"],
                            "paragraph_ref": "5",
                            "quote": "结论描述",
                            "selector_payload": {
                                "selector_type": "block",
                                "block_id": "b5",
                            },
                        }
                    ],
                },
            ],
        }
    )


class SlideDslQualityFlowTests(unittest.TestCase):
    def test_generate_valid_slides_dsl_and_pass_must_pass(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        report = validate_slides_must_pass(slides_dsl)

        self.assertEqual(len(slides_dsl.pages), 5)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.issues), 0)

    def test_must_pass_reports_specific_page_and_field(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        slides_dsl.pages[1].citations = []

        report = validate_slides_must_pass(slides_dsl)
        self.assertFalse(report.passed)
        self.assertTrue(
            any(
                item.page_index == 1 and item.field == "citations"
                for item in report.issues
            )
        )

    def test_page_level_repair_improves_quality_without_regenerating_all(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        slides_dsl.pages[2].blocks = slides_dsl.pages[2].blocks[:1]
        slides_dsl.pages[2].citations = []

        before = evaluate_slides_quality(slides_dsl)
        repaired_dsl, fix_logs = repair_low_quality_pages(
            slides_dsl, lesson_plan, before
        )
        after = evaluate_slides_quality(repaired_dsl)

        self.assertGreater(after.overall_score, before.overall_score)
        self.assertGreaterEqual(len(fix_logs), 1)
        self.assertEqual(repaired_dsl.pages[0].slide_key, slides_dsl.pages[0].slide_key)
        self.assertEqual(repaired_dsl.pages[4].slide_key, slides_dsl.pages[4].slide_key)

    def test_template_strategy_emits_shadow_scaffold_meta(self) -> None:
        lesson_plan = _lesson_plan_payload()

        _, generation_meta, shadow_report = build_slides_dsl_with_strategy(
            lesson_plan,
            strategy="template",
            llm_enabled=False,
            shadow_enabled=True,
        )

        self.assertEqual(generation_meta.requested_strategy, "template")
        self.assertEqual(generation_meta.applied_strategy, "template")
        self.assertFalse(generation_meta.fallback_used)
        self.assertEqual(shadow_report.status, "skipped")
        self.assertEqual(shadow_report.target_strategy, "llm")

    def test_llm_strategy_falls_back_to_template_when_llm_disabled(self) -> None:
        lesson_plan = _lesson_plan_payload()

        _, generation_meta, shadow_report = build_slides_dsl_with_strategy(
            lesson_plan,
            strategy="llm",
            llm_enabled=False,
            shadow_enabled=True,
        )

        self.assertEqual(generation_meta.requested_strategy, "llm")
        self.assertEqual(generation_meta.applied_strategy, "template")
        self.assertTrue(generation_meta.fallback_used)
        self.assertEqual(generation_meta.fallback_reason, "llm_disabled")
        self.assertEqual(shadow_report.status, "skipped")
        self.assertEqual(shadow_report.skip_reason, "llm_disabled")

    def test_shadow_evaluation_completes_when_llm_builder_available(self) -> None:
        lesson_plan = _lesson_plan_payload()

        def fake_llm_builder(payload: AssetLessonPlanPayload):
            candidate = build_slides_dsl(payload)
            for page in candidate.pages:
                for block in page.blocks:
                    if block.block_type == "script":
                        block.content = "基于证据的讲稿（LLM 候选）"
            return candidate

        _, generation_meta, shadow_report = build_slides_dsl_with_strategy(
            lesson_plan,
            strategy="template",
            llm_enabled=True,
            shadow_enabled=True,
            llm_builder=fake_llm_builder,
        )

        self.assertEqual(generation_meta.applied_strategy, "template")
        self.assertEqual(shadow_report.status, "completed")
        self.assertIsNotNone(shadow_report.baseline_overall_score)
        self.assertIsNotNone(shadow_report.candidate_overall_score)


if __name__ == "__main__":
    unittest.main()
