import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.slide_lesson_plan import AssetLessonPlanPayload
from app.services.slide_dsl_service import (
    build_slides_dsl,
    build_slides_dsl_via_llm,
    build_slides_dsl_with_strategy,
)
from app.services.slide_fix_service import repair_low_quality_pages
from app.services.slide_director_plan_service import build_slide_director_plan
from app.services.slide_markdown_service import build_slide_markdown_draft
from app.services.slide_outline_service import build_slide_outline
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

        self.assertGreaterEqual(len(slides_dsl.pages), 8)
        self.assertLessEqual(len(slides_dsl.pages), 16)
        self.assertEqual(slides_dsl.schema_version, "2")
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

    def test_must_pass_flags_overflow_risk_for_long_blocks(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        key_points_block = next(
            block for block in slides_dsl.pages[0].blocks if block.block_type == "key_points"
        )
        key_points_block.items = [
            "这是一个非常长的要点说明" * 8,
            "这是第二个非常长的要点说明" * 7,
        ]

        report = validate_slides_must_pass(slides_dsl)
        self.assertFalse(report.passed)
        self.assertTrue(
            any(
                item.page_index == 0 and item.code == "overflow_risk"
                for item in report.issues
            )
        )

    def test_must_pass_flags_verbatim_copy_risk_from_citation_quote(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        quote = (
            "Recurrent neural networks, long short-term memory and gated recurrent "
            "neural networks have been firmly established as state-of-the-art approaches."
        )
        slides_dsl.pages[0].citations[0].quote = quote
        evidence_block = next(
            block for block in slides_dsl.pages[0].blocks if block.block_type == "evidence"
        )
        evidence_block.items = [quote]

        report = validate_slides_must_pass(slides_dsl)

        self.assertFalse(report.passed)
        self.assertTrue(
            any(item.page_index == 0 and item.code == "verbatim_copy_risk" for item in report.issues)
        )

    def test_page_level_repair_improves_quality_without_regenerating_all(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        key_points_block = next(
            block for block in slides_dsl.pages[2].blocks if block.block_type == "key_points"
        )
        key_points_block.items = []
        slides_dsl.pages[2].citations = []

        before = evaluate_slides_quality(slides_dsl)
        repaired_dsl, fix_logs = repair_low_quality_pages(
            slides_dsl, lesson_plan, before
        )
        after = evaluate_slides_quality(repaired_dsl)

        self.assertGreater(after.overall_score, before.overall_score)
        self.assertGreaterEqual(len(fix_logs), 1)
        self.assertEqual(repaired_dsl.pages[0].slide_key, slides_dsl.pages[0].slide_key)
        self.assertEqual(
            repaired_dsl.pages[-1].slide_key,
            slides_dsl.pages[-1].slide_key,
        )

    def test_repair_splits_overflow_page_within_budget(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)
        first_key_points = next(
            block for block in slides_dsl.pages[0].blocks if block.block_type == "key_points"
        )
        first_evidence = next(
            block for block in slides_dsl.pages[0].blocks if block.block_type == "evidence"
        )
        first_key_points.items = [
            "机制解释" * 24,
            "实验观察" * 20,
            "模型行为" * 20,
            "结论约束" * 18,
        ]
        first_evidence.items = [
            "证据片段" * 30,
            "补充证据" * 26,
        ]

        before = evaluate_slides_quality(slides_dsl)
        repaired_dsl, _ = repair_low_quality_pages(slides_dsl, lesson_plan, before)

        self.assertGreater(len(repaired_dsl.pages), len(slides_dsl.pages))
        self.assertTrue(
            any(page.slide_key.endswith(":cont") for page in repaired_dsl.pages)
        )

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

    def test_llm_builder_rewrites_page_blocks_not_only_script(self) -> None:
        lesson_plan = _lesson_plan_payload()

        def fake_llm_copy(**_kwargs):
            return {
                "title": "方法亮点",
                "goal": "突出核心创新",
                "script": "先讲核心创新，再讲收益。",
                "evidence": "三个数据集平均提升 3.2%",
                "key_points": ["创新点一：并行计算", "创新点二：稳定训练"],
                "evidence_list": ["WMT14 提升 2.8 BLEU", "推理时延下降 18%"],
                "takeaway": "创新主要来自注意力机制替代循环结构。",
            }

        from unittest.mock import patch

        with (
            patch("app.services.slide_dsl_service.generate_slides_stage_copy", side_effect=fake_llm_copy),
            patch("app.services.slide_dsl_service.build_slide_director_plan", return_value={}),
        ):
            slides_dsl = build_slides_dsl_via_llm(lesson_plan)

        first_page = slides_dsl.pages[0]
        title_block = next(block for block in first_page.blocks if block.block_type == "title")
        key_points_block = next(block for block in first_page.blocks if block.block_type == "key_points")
        evidence_block = next(block for block in first_page.blocks if block.block_type == "evidence")
        takeaway_block = next(block for block in first_page.blocks if block.block_type == "takeaway")

        self.assertEqual(title_block.content, "方法亮点")
        self.assertEqual(key_points_block.items, ["创新点一：并行计算", "创新点二：稳定训练"])
        self.assertEqual(evidence_block.items, ["WMT14 提升 2.8 BLEU", "推理时延下降 18%"])
        self.assertEqual(takeaway_block.content, "创新主要来自注意力机制替代循环结构。")

    def test_director_plan_rebalances_visual_tone_when_llm_returns_single_tone(self) -> None:
        lesson_plan = _lesson_plan_payload()
        draft = build_slide_markdown_draft(build_slide_outline(lesson_plan))

        def single_tone_planner(_page):
            return {
                "layout_hint": "hero-left",
                "animation_type": "stagger_reveal",
                "target_block_type": "key_points",
                "visual_tone": "technical",
            }

        plan = build_slide_director_plan(
            draft,
            llm_enabled=True,
            planner=single_tone_planner,
        )
        tones = {hint.visual_tone for hint in plan.values()}
        self.assertGreaterEqual(len(tones), 2)


if __name__ == "__main__":
    unittest.main()
