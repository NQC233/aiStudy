import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.slide_lesson_plan import AssetLessonPlanPayload
from app.services.slide_dsl_service import (
    build_slides_dsl,
    ensure_asset_slides_schema_up_to_date,
    is_legacy_slides_dsl_payload,
)
from app.services.slide_outline_service import build_slide_outline


def _lesson_plan_payload() -> AssetLessonPlanPayload:
    return AssetLessonPlanPayload.model_validate(
        {
            "asset_id": "asset-spec15",
            "version": 3,
            "generated_at": "2026-04-11T00:00:00Z",
            "stages": [
                {
                    "stage": "problem",
                    "title": "问题背景",
                    "goal": "说明研究问题与动机",
                    "script": "介绍问题背景并明确本文要解决的核心挑战。",
                    "evidence_anchors": [
                        {
                            "page_no": 1,
                            "block_ids": ["b1"],
                            "paragraph_ref": "1",
                            "quote": "现有方法在长文本任务上性能明显下降。",
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
                    "goal": "说明方案总览和核心思路",
                    "script": "先从整体框架看输入、编码、聚合和输出的关系。",
                    "evidence_anchors": [
                        {
                            "page_no": 2,
                            "block_ids": ["b2"],
                            "paragraph_ref": "2",
                            "quote": "方法由双路编码器和门控融合模块组成。",
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
                    "goal": "解释关键模块如何生效",
                    "script": "重点展开门控融合如何抑制噪声并保留关键信息。",
                    "evidence_anchors": [
                        {
                            "page_no": 3,
                            "block_ids": ["b3"],
                            "paragraph_ref": "3",
                            "quote": "门控权重与误差下降趋势显著相关。",
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
                    "goal": "展示实验收益与对比结果",
                    "script": "对比基线、消融和不同数据规模下的表现变化。",
                    "evidence_anchors": [
                        {
                            "page_no": 4,
                            "block_ids": ["b4"],
                            "paragraph_ref": "4",
                            "quote": "在三个公开数据集上平均提升 3.2%。",
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
                    "goal": "总结贡献与后续方向",
                    "script": "归纳贡献、局限和未来可扩展方向。",
                    "evidence_anchors": [
                        {
                            "page_no": 5,
                            "block_ids": ["b5"],
                            "paragraph_ref": "5",
                            "quote": "该方法对低资源场景更具鲁棒性。",
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


class Spec15SlidesPipelineTests(unittest.TestCase):
    def test_outline_page_count_is_dynamic_and_bounded(self) -> None:
        lesson_plan = _lesson_plan_payload()

        outline = build_slide_outline(lesson_plan)

        self.assertGreaterEqual(len(outline.pages), 8)
        self.assertLessEqual(len(outline.pages), 16)

    def test_build_slides_dsl_emits_v2_schema_and_rich_blocks(self) -> None:
        lesson_plan = _lesson_plan_payload()

        slides_dsl = build_slides_dsl(lesson_plan)

        self.assertEqual(slides_dsl.schema_version, "2")
        self.assertGreaterEqual(len(slides_dsl.pages), 8)
        self.assertLessEqual(len(slides_dsl.pages), 16)
        first_page = slides_dsl.pages[0]
        block_types = {block.block_type for block in first_page.blocks}
        self.assertIn("title", block_types)
        self.assertIn("key_points", block_types)
        self.assertIn("evidence", block_types)
        self.assertIn("speaker_note", block_types)

    def test_structured_comparison_and_flow_blocks_include_data_contract(self) -> None:
        lesson_plan = _lesson_plan_payload()

        slides_dsl = build_slides_dsl(lesson_plan)

        comparison_page = next(
            (page for page in slides_dsl.pages if page.page_type == "comparison"),
            None,
        )
        flow_page = next(
            (page for page in slides_dsl.pages if page.page_type == "flow"),
            None,
        )
        if comparison_page is None or flow_page is None:
            self.fail("expected comparison and flow pages in spec15 outline")

        comparison_block = next(
            (block for block in comparison_page.blocks if block.block_type == "comparison"),
            None,
        )
        flow_block = next(
            (block for block in flow_page.blocks if block.block_type == "flow"),
            None,
        )
        if comparison_block is None or flow_block is None:
            self.fail("expected comparison and flow blocks in spec15 compiler output")
        self.assertIn("columns", comparison_block.meta)
        self.assertIn("rows", comparison_block.meta)
        self.assertGreaterEqual(len(comparison_block.meta["rows"]), 2)
        self.assertIn("steps", flow_block.meta)
        self.assertGreaterEqual(len(flow_block.meta["steps"]), 3)

    def test_key_points_are_presentation_content_not_planning_scaffold(self) -> None:
        lesson_plan = _lesson_plan_payload()

        slides_dsl = build_slides_dsl(lesson_plan)

        key_points_blocks = [
            block
            for page in slides_dsl.pages
            for block in page.blocks
            if block.block_type == "key_points"
        ]
        self.assertTrue(key_points_blocks)
        banned_phrases = ["本页目标", "先给出核心结论", "围绕"]
        for block in key_points_blocks:
            joined = " ".join(block.items)
            for phrase in banned_phrases:
                self.assertNotIn(phrase, joined)

    def test_scaffold_goal_text_is_not_leaked_to_slide_key_points(self) -> None:
        lesson_plan = _lesson_plan_payload()
        lesson_plan.stages[0].goal = "完成“问题背景”阶段讲解，帮助学习者建立主线理解。"

        slides_dsl = build_slides_dsl(lesson_plan)

        first_page_key_points = next(
            block
            for block in slides_dsl.pages[0].blocks
            if block.block_type == "key_points"
        )
        joined = " ".join(first_page_key_points.items)
        self.assertNotIn("完成“问题背景”阶段讲解", joined)
        self.assertNotIn("学习者", joined)

    def test_key_points_first_line_includes_page_title_context(self) -> None:
        lesson_plan = _lesson_plan_payload()
        slides_dsl = build_slides_dsl(lesson_plan)

        first_page = slides_dsl.pages[0]
        second_page = slides_dsl.pages[1]
        first_points = next(
            block.items for block in first_page.blocks if block.block_type == "key_points"
        )
        second_points = next(
            block.items for block in second_page.blocks if block.block_type == "key_points"
        )
        self.assertTrue(first_points[0].startswith(first_page.blocks[0].content))
        self.assertTrue(second_points[0].startswith(second_page.blocks[0].content))
        self.assertNotEqual(first_points[0], second_points[0])

    def test_legacy_payload_detection_supports_auto_rebuild_gate(self) -> None:
        legacy_payload = {
            "asset_id": "asset-spec15",
            "version": 1,
            "generated_at": "2026-04-01T00:00:00Z",
            "pages": [],
        }
        self.assertTrue(is_legacy_slides_dsl_payload(legacy_payload))
        self.assertFalse(
            is_legacy_slides_dsl_payload(
                {
                    "schema_version": "2",
                    "asset_id": "asset-spec15",
                    "version": 3,
                    "generated_at": "2026-04-11T00:00:00Z",
                    "pages": [],
                }
            )
        )

    def test_auto_rebuild_enqueues_when_legacy_payload_detected(self) -> None:
        asset = SimpleNamespace(id="asset-spec15", slides_status="ready")
        presentation = SimpleNamespace(slides_dsl={"asset_id": "asset-spec15"})

        class ScalarResult:
            def first(self):
                return presentation

        class FakeDb:
            def scalars(self, _statement):
                return ScalarResult()

        fake_db: Any = FakeDb()
        with (
            patch("app.services.slide_dsl_service._require_asset", return_value=asset),
            patch(
                "app.services.slide_lesson_plan_service.enqueue_asset_lesson_plan_rebuild",
                return_value=(asset, True, "queued"),
            ) as enqueue_mock,
        ):
            rebuilt_asset, enqueued, _message = ensure_asset_slides_schema_up_to_date(
                fake_db,
                "asset-spec15",
            )

        self.assertTrue(enqueued)
        self.assertEqual(rebuilt_asset.id, "asset-spec15")
        enqueue_mock.assert_called_once()

    def test_auto_rebuild_skips_when_payload_already_v2(self) -> None:
        asset = SimpleNamespace(id="asset-spec15", slides_status="ready")
        presentation = SimpleNamespace(
            slides_dsl={
                "schema_version": "2",
                "asset_id": "asset-spec15",
                "version": 3,
                "generated_at": "2026-04-11T00:00:00Z",
                "pages": [],
            }
        )

        class ScalarResult:
            def first(self):
                return presentation

        class FakeDb:
            def scalars(self, _statement):
                return ScalarResult()

        fake_db: Any = FakeDb()
        with (
            patch("app.services.slide_dsl_service._require_asset", return_value=asset),
            patch(
                "app.services.slide_lesson_plan_service.enqueue_asset_lesson_plan_rebuild",
            ) as enqueue_mock,
        ):
            rebuilt_asset, enqueued, _message = ensure_asset_slides_schema_up_to_date(
                fake_db,
                "asset-spec15",
            )

        self.assertFalse(enqueued)
        self.assertEqual(rebuilt_asset.id, "asset-spec15")
        enqueue_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
