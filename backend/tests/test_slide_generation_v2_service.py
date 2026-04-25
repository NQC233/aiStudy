import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.document_chunk import AssetRetrievalSearchResponse
from app.schemas.document_chunk import RetrievalSearchHit
from app.schemas.slide_dsl import SlidesRuntimeBundle
from app.services.slide_generation_v2_service import finalize_rendered_slide_pages_for_runtime
from app.services.slide_generation_v2_service import generate_asset_slides_runtime_bundle
from app.services.slide_generation_v2_service import repair_rendered_slide_pages
from app.services.slide_planning_service import build_presentation_plan
from app.services.slide_runtime_bundle_service import build_runtime_bundle
from app.services.slide_runtime_bundle_service import summarize_runtime_bundle


class _ScalarResult:
    def __init__(self, obj):
        self.obj = obj

    def first(self):
        return self.obj


class _FakeDb:
    def __init__(self, asset, presentation):
        self._asset = asset
        self._presentation = presentation
        self.commit_count = 0

    def get(self, model, asset_id):  # noqa: ANN001
        return self._asset if asset_id == self._asset.id else None

    def scalars(self, _statement):  # noqa: ANN001
        return _ScalarResult(self._presentation)

    def add(self, obj):  # noqa: ANN001
        self._presentation = obj

    def commit(self):
        self.commit_count += 1

    def refresh(self, _obj):  # noqa: ANN001
        return None


class _CommitTrackingDb(_FakeDb):
    def __init__(self, asset, presentation):
        super().__init__(asset, presentation)
        self.asset_status_history: list[str] = []
        self.presentation_status_history: list[str] = []

    def commit(self):
        self.asset_status_history.append(getattr(self._asset, "slides_status", ""))
        self.presentation_status_history.append(getattr(self._presentation, "status", ""))
        super().commit()


class _StrictJsonDb(_FakeDb):
    def commit(self):
        import json

        json.dumps(self._presentation.analysis_pack)
        super().commit()


class SlideGenerationV2ServiceTests(unittest.TestCase):
    def test_runtime_bundle_schema_accepts_batch_metadata(self) -> None:
        bundle = SlidesRuntimeBundle.model_validate(
            {
                "page_count": 1,
                "pages": [],
                "playable_page_count": 0,
                "failed_page_numbers": [],
                "validation_summary": {"status": "not_ready"},
                "deck_meta": {"typography": {"title_scale": 42}},
                "generation_meta": {
                    "html_generation_mode": "batch",
                    "html_batch_count": 1,
                },
            }
        )

        self.assertEqual(bundle.deck_meta["typography"]["title_scale"], 42)
        self.assertEqual(bundle.generation_meta["html_generation_mode"], "batch")

    def test_summarize_runtime_bundle_prefers_page_level_validation_over_stale_failed_pages(self) -> None:
        summary = summarize_runtime_bundle(
            {
                "page_count": 2,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>One</section>",
                        "css": ".one{}",
                        "asset_refs": [],
                        "render_meta": {
                            "validation": {
                                "status": "passed",
                                "blocking": False,
                                "reason": None,
                            },
                            "runtime_gate_status": "ready",
                        },
                    },
                    {
                        "page_id": "page-2",
                        "html": "<section>Two</section>",
                        "css": ".two{}",
                        "asset_refs": [],
                        "render_meta": {
                            "validation": {
                                "status": "passed",
                                "blocking": False,
                                "reason": None,
                            },
                            "runtime_gate_status": "ready",
                        },
                    },
                ],
                "playable_page_count": 1,
                "failed_page_numbers": [2],
                "validation_summary": {
                    "status": "not_ready",
                    "page_count": 2,
                    "playable_page_count": 1,
                    "failed_page_numbers": [2],
                },
            }
        )

        self.assertEqual(summary["playable_page_count"], 2)
        self.assertEqual(summary["failed_page_numbers"], [])
        self.assertEqual(summary["validation_summary"]["status"], "ready")

    def test_finalize_rendered_slide_pages_for_runtime_applies_validation_before_bundle_build(self) -> None:
        rendered_pages = [
            {
                "page_id": "page-1",
                "html": "<html><body><div class='slide-root'>OK</div></body></html>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            {
                "page_id": "page-2",
                "html": "<html><body><div class='slide-root broken'>BAD</div></body></html>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
        ]

        bundle = finalize_rendered_slide_pages_for_runtime(
            rendered_pages,
            canvas_width=1600,
            canvas_height=900,
            validation_enabled=True,
            validate_page_html=lambda **kwargs: {
                1: {"status": "passed", "blocking": False, "reason": None},
                2: {
                    "status": "failed",
                    "blocking": True,
                    "reason": "overflow_detected",
                },
            }[kwargs["page_number"]],
            runtime_bundle_builder=build_runtime_bundle,
        )

        self.assertEqual(rendered_pages[0]["render_meta"]["canvas"], {"width": 1600, "height": 900})
        self.assertEqual(rendered_pages[0]["render_meta"]["validation"]["status"], "passed")
        self.assertEqual(rendered_pages[1]["render_meta"]["validation"]["status"], "failed")
        self.assertEqual(rendered_pages[1]["render_meta"]["runtime_gate_status"], "failed")
        self.assertEqual(bundle["playable_page_count"], 1)
        self.assertEqual(bundle["failed_page_numbers"], [2])

    def test_repair_rendered_slide_pages_keeps_trimmed_page_without_rewrite(self) -> None:
        pages = [
            {
                "page_id": "page-1",
                "page_number": 1,
                "html": "<section>ok</section>",
                "css": ".page{}",
                "render_meta": {
                    "validation": {"status": "passed", "blocking": False, "reason": None},
                    "repair_hints": {"status": "trimmed", "overflow_residue": []},
                },
            }
        ]

        repaired = repair_rendered_slide_pages(
            pages,
            rewrite_page_html=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("rewrite should not run")),
            max_total_extra_pages=3,
        )

        self.assertEqual(repaired[0]["render_meta"]["repair_state"], "trimmed_ok")

    def test_repair_rendered_slide_pages_rewrites_failed_page_once(self) -> None:
        pages = [
            {
                "page_id": "page-2",
                "page_number": 2,
                "html": "<section>bad</section>",
                "css": ".page{}",
                "render_meta": {
                    "validation": {"status": "failed", "blocking": True, "reason": "overflow_detected"},
                    "repair_hints": {"status": "trimmed", "overflow_residue": [{"type": "bullets", "items": ["extra"]}]},
                },
            }
        ]

        repaired = repair_rendered_slide_pages(
            pages,
            rewrite_page_html=lambda page, *_args, **_kwargs: {
                **page,
                "html": "<section>rewritten</section>",
                "render_meta": {
                    **page["render_meta"],
                    "validation": {"status": "passed", "blocking": False, "reason": None},
                },
            },
            max_total_extra_pages=3,
        )

        self.assertEqual(repaired[0]["html"], "<section>rewritten</section>")
        self.assertEqual(repaired[0]["render_meta"]["repair_state"], "rewritten_ok")

    def test_repair_rendered_slide_pages_adds_continuation_page_when_rewrite_still_fails(self) -> None:
        pages = [
            {
                "page_id": "page-2",
                "page_number": 2,
                "html": "<section>bad</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {
                    "validation": {"status": "failed", "blocking": True, "reason": "overflow_detected"},
                    "repair_hints": {"status": "trimmed", "overflow_residue": [{"type": "bullets", "items": ["extra"]}]},
                },
            }
        ]

        repaired = repair_rendered_slide_pages(
            pages,
            rewrite_page_html=lambda page, *_args, **_kwargs: {
                **page,
                "render_meta": {
                    **page["render_meta"],
                    "validation": {"status": "failed", "blocking": True, "reason": "overflow_detected"},
                },
            },
            max_total_extra_pages=3,
        )

        self.assertEqual(repaired[0]["render_meta"]["repair_state"], "failed_after_rewrite")
        self.assertEqual(repaired[1]["page_id"], "page-2-cont-1")
        self.assertEqual(repaired[1]["render_meta"]["repair_state"], "split_continuation")

    def test_generate_asset_slides_runtime_bundle_repairs_failed_page_with_continuation(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "method",
                        "narrative_goal": "intro",
                        "visual_strategy": "text_only",
                        "page_budget": {
                            "max_blocks": 1,
                            "content_budget": {"bullet_max_items": 1},
                            "overflow_strategy": {"mode": "trim_then_split"},
                            "continuation_policy": {"enabled": True, "max_extra_pages": 3},
                        },
                    }
                ],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {
                    "page_id": "page-1",
                    "title": "Transformer",
                    "summary_line": "Intro",
                    "layout_strategy": "hero",
                    "content_blocks": [
                        {"type": "bullets", "items": ["A", "B"]},
                    ],
                    "page_budget": {
                        "max_blocks": 1,
                        "content_budget": {"bullet_max_items": 1},
                        "overflow_strategy": {"mode": "trim_then_split"},
                        "continuation_policy": {"enabled": True, "max_extra_pages": 3},
                    },
                }
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>overflow</section>",
                "css": (
                    "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                    ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ),
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=build_runtime_bundle,
        )

        self.assertEqual(result["rendered_slide_pages"][0]["render_meta"]["repair_state"], "failed_after_rewrite")
        self.assertEqual(result["rendered_slide_pages"][1]["page_id"], "page-1-cont-1")
        self.assertEqual(result["rendered_slide_pages"][1]["render_meta"]["repair_state"], "split_continuation")
        self.assertEqual(result["runtime_bundle"]["page_count"], 2)
        self.assertEqual(result["runtime_bundle"]["pages"][1]["page_id"], "page-1-cont-1")

    def test_generate_asset_slides_runtime_bundle_marks_processing_before_generation(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        db = _CommitTrackingDb(asset, presentation)

        generate_asset_slides_runtime_bundle(
            db,
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer", "summary_line": "Intro", "layout_strategy": "hero"}
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": (
                    "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                    ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ),
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(db.presentation_status_history[0], "processing")
        self.assertEqual(db.presentation_status_history[-1], "ready")

    def test_generate_asset_slides_runtime_bundle_can_stop_after_analysis_layer(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: calls.append("analysis") or {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            visual_asset_builder=lambda *_args, **_kwargs: calls.append("visual") or [],
            plan_builder=lambda *_args, **_kwargs: calls.append("plan") or {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: calls.append("scene") or [],
            html_renderer=lambda *_args, **_kwargs: calls.append("html") or {
                "page_id": "page-1",
                "html": "<section></section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
            debug_target="analysis",
        )

        self.assertEqual(calls, ["analysis", "visual"])
        self.assertTrue(result["analysis_pack"])
        self.assertEqual(result["presentation_plan"], {})
        self.assertEqual(result["scene_specs"], [])
        self.assertEqual(result["rendered_slide_pages"], [])
        self.assertEqual(result["runtime_bundle"]["page_count"], 0)
        self.assertEqual(result["slides_status"], "processing")
        self.assertEqual(asset.slides_status, "processing")
        self.assertEqual(presentation.status, "processing")
        self.assertEqual(result["error_meta"]["debug_target"], "analysis")

    def test_generate_asset_slides_runtime_bundle_can_stop_after_plan_layer(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: calls.append("analysis") or {
                "core_claims": ["Transformers remove recurrence."],
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            visual_asset_builder=lambda *_args, **_kwargs: calls.append("visual") or [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: calls.append("plan") or {
                "page_count": 4,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "cover",
                        "narrative_goal": "介绍论文价值",
                        "content_focus": "problem",
                        "visual_strategy": "text_only",
                        "candidate_assets": [],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
            scene_builder=lambda *_args, **_kwargs: calls.append("scene") or [],
            html_renderer=lambda *_args, **_kwargs: calls.append("html") or {
                "page_id": "page-1",
                "html": "<section></section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
            debug_target="plan",
        )

        self.assertEqual(calls, ["analysis", "visual", "plan"])
        self.assertTrue(result["presentation_plan"])
        self.assertEqual(result["scene_specs"], [])
        self.assertEqual(result["rendered_slide_pages"], [])
        self.assertEqual(result["runtime_bundle"]["page_count"], 0)
        self.assertEqual(result["slides_status"], "processing")
        self.assertEqual(asset.slides_status, "processing")
        self.assertEqual(presentation.status, "processing")
        self.assertEqual(result["error_meta"]["debug_target"], "plan")


    def test_generate_asset_slides_runtime_bundle_marks_scene_debug_run_as_processing(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer", "summary_line": "Intro", "layout_strategy": "hero"}
            ],
            html_renderer=lambda *_args, **_kwargs: self.fail("html layer should not run for scene debug target"),
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
            debug_target="scene",
        )

        self.assertEqual(result["slides_status"], "processing")
        self.assertEqual(result["runtime_bundle"]["page_count"], 0)
        self.assertTrue(result["scene_specs"])
        self.assertEqual(asset.slides_status, "processing")
        self.assertEqual(presentation.status, "processing")

    def test_generate_asset_slides_runtime_bundle_marks_empty_runtime_bundle_as_failed(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer", "summary_line": "Intro", "layout_strategy": "hero"}
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda _rendered_pages: {"page_count": 0, "pages": []},
        )

        self.assertEqual(result["slides_status"], "failed")
        self.assertEqual(asset.slides_status, "failed")
        self.assertEqual(presentation.status, "failed")
        self.assertEqual(result["runtime_bundle"]["page_count"], 0)

    def test_generate_asset_slides_runtime_bundle_marks_blocked_runtime_bundle_as_failed(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer", "summary_line": "Intro", "layout_strategy": "hero"}
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {
                "page_count": len(rendered_pages),
                "pages": [
                    {
                        **rendered_pages[0],
                        "render_meta": {
                            **rendered_pages[0].get("render_meta", {}),
                            "validation": {"status": "failed", "reason": "overflow"},
                        },
                    }
                ],
                "playable_page_count": 0,
                "failed_page_numbers": [1],
                "validation_summary": {
                    "status": "not_ready",
                    "page_count": len(rendered_pages),
                    "playable_page_count": 0,
                    "failed_page_numbers": [1],
                },
            },
        )

        self.assertEqual(result["slides_status"], "failed")
        self.assertEqual(asset.slides_status, "failed")
        self.assertEqual(presentation.status, "failed")
        self.assertEqual(result["runtime_bundle"]["failed_page_numbers"], [1])

    def test_generate_asset_slides_runtime_bundle_marks_partially_failed_runtime_bundle_as_ready(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 2,
                "pages": [
                    {"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro-1"},
                    {"page_id": "page-2", "scene_role": "cover", "narrative_goal": "intro-2"},
                ],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer 1", "summary_line": "Intro 1", "layout_strategy": "hero"},
                {"page_id": "page-2", "title": "Transformer 2", "summary_line": "Intro 2", "layout_strategy": "hero"},
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": f"<section>{scene_spec['title']}</section>",
                "css": (
                    "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                    ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ),
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {
                "page_count": len(rendered_pages),
                "pages": [
                    rendered_pages[0],
                    {
                        **rendered_pages[1],
                        "render_meta": {
                            **rendered_pages[1].get("render_meta", {}),
                            "validation": {"status": "failed", "reason": "overflow"},
                        },
                    },
                ],
                "playable_page_count": 1,
                "failed_page_numbers": [2],
                "validation_summary": {
                    "status": "not_ready",
                    "page_count": len(rendered_pages),
                    "playable_page_count": 1,
                    "failed_page_numbers": [2],
                },
            },
        )

        self.assertEqual(result["slides_status"], "ready")
        self.assertEqual(asset.slides_status, "ready")
        self.assertEqual(presentation.status, "ready")
        self.assertEqual(result["runtime_bundle"]["playable_page_count"], 1)
        self.assertEqual(result["runtime_bundle"]["failed_page_numbers"], [2])
        self.assertEqual(result["runtime_bundle"]["validation_summary"]["status"], "partial_ready")

    def test_generate_asset_slides_runtime_bundle_uses_real_query_family_search_contract(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        search_calls: list[tuple[str, str, int, bool, str]] = []

        def _search(db, asset_id: str, query: str, top_k: int, rewrite_query: bool, strategy: str):  # noqa: ANN001
            search_calls.append((asset_id, query, top_k, rewrite_query, strategy))
            return AssetRetrievalSearchResponse(asset_id=asset_id, query=query, top_k=top_k, results=[])

        generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            search_func=_search,
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer", "summary_line": "Intro", "layout_strategy": "hero"}
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertTrue(search_calls)
        self.assertEqual(search_calls[0][0], "asset-1")
        self.assertEqual(search_calls[0][2], 3)
        self.assertFalse(search_calls[0][3])
        self.assertEqual(search_calls[0][4], "s0")

    def test_generate_asset_slides_runtime_bundle_default_scene_builder_receives_real_context(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        captured_scene_context: dict[str, object] = {}

        generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {
                    "images": [
                        {
                            "resource_id": "fig-1",
                            "type": "image",
                            "page_no": 2,
                            "block_id": "blk-fig-1",
                            "caption": ["Figure 1. Transformer architecture."],
                            "public_url": "https://example.com/fig-1.png",
                        }
                    ],
                    "tables": [],
                },
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {
                    "asset_id": "fig-1",
                    "recommended_usage": "method_overview",
                    "vision_summary": "Transformer architecture figure.",
                    "page_no": 2,
                    "block_id": "blk-fig-1",
                }
            ],
            llm_enabled=True,
            llm_plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "method", "narrative_goal": "Explain architecture."}],
            },
            llm_scene_builder=lambda presentation_plan, analysis_pack, visual_asset_catalog: captured_scene_context.update(
                {
                    "presentation_plan": presentation_plan,
                    "analysis_pack": analysis_pack,
                    "visual_asset_catalog": visual_asset_catalog,
                }
            ) or [
                {
                    "page_id": "page-1",
                    "title": "Transformer Architecture",
                    "summary_line": analysis_pack["main_results"][0],
                    "layout_strategy": "hero-visual-right",
                    "asset_bindings": [{"asset_id": visual_asset_catalog[0]["asset_id"]}],
                }
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": scene_spec.get("asset_bindings", []),
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(captured_scene_context["analysis_pack"]["main_results"][0], "Better BLEU with less training cost.")
        self.assertEqual(captured_scene_context["visual_asset_catalog"][0]["asset_id"], "fig-1")

    def test_generate_asset_slides_runtime_bundle_uses_batch_html_for_full_generation(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle={},
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        batch_calls: list[list[str]] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={"blocks": [], "assets": {"images": [], "tables": []}},
            analysis_builder=lambda *_args, **_kwargs: {"problem_statements": ["A"]},
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 2,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "problem",
                        "narrative_goal": "A",
                        "visual_strategy": "text_only",
                    },
                    {
                        "page_id": "page-2",
                        "scene_role": "method",
                        "narrative_goal": "B",
                        "visual_strategy": "text_only",
                    },
                ],
            },
            scene_builder=lambda presentation_plan, **_kwargs: [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": presentation_plan["pages"][0]["narrative_goal"],
                    "summary_line": presentation_plan["pages"][0]["narrative_goal"],
                    "content_blocks": [],
                }
            ],
            batch_html_renderer=lambda scene_specs, **_kwargs: batch_calls.append(
                [item["page_id"] for item in scene_specs]
            ) or {
                "deck_meta": {"typography": {"title_scale": 42}},
                "pages": [
                    {
                        "page_id": item["page_id"],
                        "html": f"<section>{item['title']}</section>",
                        "css": (
                            "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                            ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                        ),
                        "asset_refs": [],
                        "render_meta": {},
                    }
                    for item in scene_specs
                ],
            },
            runtime_bundle_builder=build_runtime_bundle,
        )

        self.assertEqual(batch_calls, [["page-1", "page-2"]])
        self.assertEqual(result["runtime_bundle"]["deck_meta"]["typography"]["title_scale"], 42)
        self.assertEqual(result["runtime_bundle"]["generation_meta"]["html_generation_mode"], "batch")

    def test_generate_asset_slides_runtime_bundle_prefers_llm_builders_when_enabled(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {
                    "images": [
                        {
                            "resource_id": "fig-1",
                            "type": "image",
                            "page_no": 2,
                            "block_id": "blk-fig-1",
                            "caption": ["Figure 1. Transformer architecture."],
                            "public_url": "https://example.com/fig-1.png",
                        }
                    ],
                    "tables": [],
                },
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {
                    "asset_id": "fig-1",
                    "recommended_usage": "method_overview",
                    "vision_summary": "Transformer architecture figure.",
                    "page_no": 2,
                    "block_id": "blk-fig-1",
                }
            ],
            llm_enabled=True,
            llm_plan_builder=lambda analysis_pack, visual_asset_catalog: calls.append("plan") or {
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "method",
                        "narrative_goal": analysis_pack["method_components"][0],
                        "content_focus": "method_overview",
                        "visual_strategy": "text_plus_original_figure",
                        "candidate_assets": [visual_asset_catalog[0]["asset_id"]],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
            llm_scene_builder=lambda presentation_plan, analysis_pack, visual_asset_catalog: calls.append("scene") or [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": "Transformer Architecture",
                    "summary_line": analysis_pack["main_results"][0],
                    "layout_strategy": "hero-visual-right",
                    "content_blocks": [
                        {"type": "bullets", "items": [analysis_pack["method_components"][0]]}
                    ],
                    "citations": [{"page_no": 3, "block_ids": ["b3"]}],
                    "asset_bindings": [{"asset_id": visual_asset_catalog[0]["asset_id"]}],
                    "animation_plan": {"type": "soft_intro"},
                    "speaker_note_seed": "Explain the encoder-decoder split.",
                }
            ],
            llm_html_renderer=lambda scene_spec: calls.append("html") or {
                "page_id": scene_spec["page_id"],
                "html": f"<section><h1>{scene_spec['title']}</h1><p>{scene_spec['summary_line']}</p></section>",
                "css": (
                    "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                    ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ),
                "asset_refs": scene_spec.get("asset_bindings", []),
                "render_meta": {"mode": "llm"},
            },
            plan_builder=lambda *_args, **_kwargs: self.fail("template plan builder should not run"),
            scene_builder=lambda *_args, **_kwargs: self.fail("template scene builder should not run"),
            html_renderer=lambda *_args, **_kwargs: self.fail("template html renderer should not run"),
            batch_html_renderer=lambda scene_specs, **_kwargs: {
                "deck_meta": {},
                "pages": [
                    {
                        "page_id": scene_specs[0]["page_id"],
                        "html": f"<section><h1>{scene_specs[0]['title']}</h1><p>{scene_specs[0]['summary_line']}</p></section>",
                        "css": (
                            "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                            ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                        ),
                        "asset_refs": scene_specs[0].get("asset_bindings", []),
                        "render_meta": {"mode": "llm"},
                    }
                ],
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(calls, ["plan", "scene"])
        self.assertEqual(result["runtime_bundle"]["pages"][0]["render_meta"]["mode"], "llm")

    def test_page_scoped_html_rebuild_reuses_persisted_deck_meta(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={
                "page_count": 2,
                "pages": [],
                "playable_page_count": 1,
                "failed_page_numbers": [2],
                "validation_summary": {"status": "partial_ready"},
                "deck_meta": {"typography": {"title_scale": 42}, "spacing": {"page_padding_x": 88}},
            },
            analysis_pack={"problem_statements": ["A"]},
            visual_asset_catalog=[],
            presentation_plan={
                "page_count": 2,
                "pages": [
                    {"page_id": "page-1", "scene_role": "problem", "narrative_goal": "A", "visual_strategy": "text_only"},
                    {"page_id": "page-2", "scene_role": "method", "narrative_goal": "B", "visual_strategy": "text_only"},
                ],
            },
            scene_specs=[
                {"page_id": "page-1", "title": "问题", "summary_line": "A", "content_blocks": []},
                {"page_id": "page-2", "title": "方法", "summary_line": "B", "content_blocks": []},
            ],
            rendered_slide_pages=[
                {"page_id": "page-1", "html": "<section>问题</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>旧方法</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
            ],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        seen_style_guides: list[dict[str, object]] = []

        generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="html",
            page_numbers=[2],
            reuse_analysis_pack=True,
            reuse_presentation_plan=True,
            html_renderer=lambda scene_spec, deck_style_guide=None, **_kwargs: seen_style_guides.append(deck_style_guide) or {
                "page_id": scene_spec["page_id"],
                "html": "<section>新方法</section>",
                "css": (
                    "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                    ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ),
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=build_runtime_bundle,
        )

        self.assertEqual(seen_style_guides[0]["deck_meta"]["typography"]["title_scale"], 42)

    def test_failed_only_rebuild_rejects_when_failed_ratio_exceeds_threshold(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={
                "page_count": 4,
                "pages": [
                    {
                        "page_id": f"page-{index}",
                        "html": f"<section>{index}</section>",
                        "css": (
                            "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                            ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                        ),
                        "asset_refs": [],
                        "render_meta": {},
                    }
                    for index in range(1, 5)
                ],
                "playable_page_count": 2,
                "failed_page_numbers": [1, 2],
                "validation_summary": {"status": "partial_ready"},
                "deck_meta": {},
            },
            analysis_pack={"problem_statements": ["A"]},
            visual_asset_catalog=[],
            presentation_plan={"page_count": 4, "pages": [{"page_id": f"page-{index}"} for index in range(1, 5)]},
            scene_specs=[{"page_id": f"page-{index}", "title": str(index), "summary_line": str(index), "content_blocks": []} for index in range(1, 5)],
            rendered_slide_pages=[],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        with self.assertRaisesRegex(ValueError, "failed_only rebuild exceeds threshold"):
            generate_asset_slides_runtime_bundle(
                _FakeDb(asset, presentation),
                asset_id="asset-1",
                from_stage="html",
                failed_only=True,
                reuse_analysis_pack=True,
                reuse_presentation_plan=True,
            )
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _StrictJsonDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "query_family_hits": {
                    "paper_motivation": [
                        RetrievalSearchHit(
                            chunk_id="c-problem",
                            score=0.9,
                            text="Recurrence slows training.",
                            page_start=2,
                            page_end=2,
                            block_ids=["b-problem"],
                            section_path=["Introduction"],
                            quote_text="Recurrence slows training.",
                        )
                    ]
                },
                "problem_statements": ["Recurrence slows training."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {"page_id": "page-1", "title": "Transformer", "summary_line": "Intro", "layout_strategy": "hero"}
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(result["analysis_pack"]["query_family_hits"]["paper_motivation"][0]["chunk_id"], "c-problem")

    def test_generate_asset_slides_runtime_bundle_records_scene_and_html_fallbacks_in_error_meta(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "method_steps": ["Encode tokens.", "Apply attention blocks."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [{"page_id": "page-1", "scene_role": "cover", "narrative_goal": "intro"}],
            },
            scene_builder=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("scene boom")),
            batch_html_renderer=lambda *_args, **_kwargs: {
                "deck_meta": {"theme_name": "paper-academic"},
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section class=\"slide-page\"><h1>Recurrence slows training.</h1><p>Recurrence slows training.</p></section>",
                        "css": ".slide-page{width:100%;height:100%;box-sizing:border-box;padding:72px 88px;background:#fff;color:#1f2937;font-family:Inter,system-ui,sans-serif;}.slide-page h1{margin:0 0 24px;font-size:42px;line-height:1.1;}.slide-page p{margin:0;font-size:24px;line-height:1.5;}",
                        "asset_refs": [],
                        "render_meta": {"layout_strategy": "hero-text"},
                    }
                ],
                "html_meta": [
                    {"page_id": "page-1", "status": "fallback", "reason": "html boom"}
                ],
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(result["scene_specs"][0]["title"], "Recurrence slows training.")
        self.assertEqual(result["runtime_bundle"]["page_count"], 1)
        self.assertEqual(result["error_meta"]["scene_generation"][0]["status"], "fallback")
        self.assertIn("scene boom", result["error_meta"]["scene_generation"][0]["reason"])
        self.assertEqual(result["error_meta"]["html_generation"][0]["status"], "fallback")
        self.assertIn("html boom", result["error_meta"]["html_generation"][0]["reason"])

    def test_generate_asset_slides_runtime_bundle_records_plan_fallback_in_error_meta(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "method_steps": ["Encode tokens.", "Apply attention blocks."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("plan boom")),
            scene_builder=lambda presentation_plan, **_kwargs: [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": presentation_plan["pages"][0]["narrative_goal"],
                    "summary_line": presentation_plan["pages"][0]["narrative_goal"],
                    "layout_strategy": "hero-text",
                    "content_blocks": [],
                    "citations": [],
                    "asset_bindings": [],
                    "animation_plan": {"type": "soft_intro"},
                    "speaker_note_seed": "intro",
                }
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertGreaterEqual(result["presentation_plan"]["page_count"], 4)
        self.assertEqual(result["error_meta"]["plan_generation"][0]["status"], "fallback")
        self.assertIn("plan boom", result["error_meta"]["plan_generation"][0]["reason"])

    def test_generate_asset_slides_runtime_bundle_records_empty_plan_as_fallback(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "method_steps": ["Encode tokens.", "Apply attention blocks."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: {"page_count": 0, "pages": []},
            scene_builder=lambda presentation_plan, **_kwargs: [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": presentation_plan["pages"][0]["narrative_goal"],
                    "summary_line": presentation_plan["pages"][0]["narrative_goal"],
                    "layout_strategy": "hero-text",
                    "content_blocks": [],
                    "citations": [],
                    "asset_bindings": [],
                    "animation_plan": {"type": "soft_intro"},
                    "speaker_note_seed": "intro",
                }
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": "<section>Transformer</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(result["error_meta"]["plan_generation"][0]["status"], "fallback")
        self.assertIn("presentation plan pages cannot be empty", result["error_meta"]["plan_generation"][0]["reason"])
        self.assertGreaterEqual(result["presentation_plan"]["page_count"], 4)

    def test_generate_asset_slides_runtime_bundle_preserves_original_plan_failure_reason(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "method_steps": ["Encode tokens.", "Apply attention blocks."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("planner timeout")),
            scene_builder=lambda presentation_plan, **_kwargs: [
                {"page_id": page["page_id"], "title": page["narrative_goal"], "summary_line": page["narrative_goal"], "layout_strategy": "hero-text"}
                for page in presentation_plan["pages"]
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": f"<section>{scene_spec['title']}</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(result["error_meta"]["plan_generation"][0]["status"], "fallback")
        self.assertIn("planner timeout", result["error_meta"]["plan_generation"][0]["reason"])
        self.assertGreaterEqual(result["presentation_plan"]["page_count"], 4)

    def test_generate_asset_slides_runtime_bundle_marks_plan_fallback_usage_explicitly(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "method_steps": ["Encode tokens.", "Apply attention blocks."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("planner transport error")),
            scene_builder=lambda presentation_plan, **_kwargs: [
                {"page_id": page["page_id"], "title": page["narrative_goal"], "summary_line": page["narrative_goal"], "layout_strategy": "hero-text"}
                for page in presentation_plan["pages"]
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": f"<section>{scene_spec['title']}</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        plan_meta = result["error_meta"]["plan_generation"][0]
        self.assertEqual(plan_meta["status"], "fallback")
        self.assertTrue(plan_meta["fallback_used"])
        self.assertEqual(plan_meta["planner_error"], "planner transport error")

    def test_generate_asset_slides_runtime_bundle_surfaces_internal_plan_fallback_diagnostics(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "method_steps": ["Encode tokens.", "Apply attention blocks."],
                "main_results": ["Better BLEU with less training cost."],
                "ablations": ["Removing multi-head attention hurts BLEU."],
                "limitations": ["Quadratic complexity for long sequences."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda analysis_pack, visual_asset_catalog, **_kwargs: build_presentation_plan(
                analysis_pack,
                visual_asset_catalog,
                plan_writer=lambda *_args, **_kwargs: {
                    "page_count": 1,
                    "pages": [
                        {
                            "page_id": "page-1",
                            "scene_role": "overview",
                            "narrative_goal": "Paper Overview",
                            "content_focus": "overview",
                            "visual_strategy": "text_only",
                            "candidate_assets": [],
                            "animation_intent": "soft_intro",
                        }
                    ],
                },
            ),
            scene_builder=lambda *_args, **_kwargs: [],
            html_renderer=lambda *_args, **_kwargs: self.fail("html should not run"),
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
            debug_target="plan",
        )

        plan_meta = result["error_meta"]["plan_generation"][0]
        self.assertEqual(result["presentation_plan"]["page_count"], 4)
        self.assertEqual(plan_meta["status"], "success")
        self.assertFalse(plan_meta["fallback_used"])
        self.assertEqual(plan_meta["planner_status"], "success")
        self.assertTrue(plan_meta["internal_fallback_used"])
        self.assertEqual(plan_meta["plan_source"], "fallback")
        self.assertEqual(plan_meta["raw_page_count"], 1)
        self.assertEqual(plan_meta["validated_page_count"], 4)
        self.assertIn("presentation plan collapsed rich analysis into too few pages", plan_meta["internal_error"])

    def test_generate_asset_slides_runtime_bundle_surfaces_empty_scene_diagnostics(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
                "evidence_catalog": [{"family_key": "method_overview", "chunk_id": "c1"}],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [
                {"asset_id": "fig-1", "recommended_usage": "method_overview"}
            ],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "method",
                        "narrative_goal": "解释架构",
                        "content_focus": "method_components",
                        "visual_strategy": "text_plus_original_figure",
                        "candidate_assets": ["fig-1"],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
            scene_builder=lambda *_args, **_kwargs: [
                {
                    "page_id": "page-1",
                    "title": "解释架构",
                    "summary_line": "解释架构",
                    "layout_strategy": "hero-visual-right",
                    "content_blocks": [],
                    "citations": [],
                    "asset_bindings": [{"asset_id": "fig-1"}],
                    "animation_plan": {"type": "soft_intro"},
                    "speaker_note_seed": "解释架构",
                }
            ],
            html_renderer=lambda *_args, **_kwargs: self.fail("html should not run"),
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
            debug_target="scene",
        )

        scene_meta = result["error_meta"]["scene_generation"][0]
        self.assertEqual(scene_meta["status"], "success")
        self.assertEqual(scene_meta["scene_source"], "generated")
        self.assertTrue(scene_meta["is_empty_scene"])
        self.assertEqual(scene_meta["content_blocks_count"], 0)
        self.assertEqual(scene_meta["citations_count"], 0)
        self.assertEqual(scene_meta["asset_bindings_count"], 1)

    def test_generate_asset_slides_runtime_bundle_propagates_deck_style_guide_to_scene_and_html_layers(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        seen: dict[str, object] = {}

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 1,
                "deck_style_guide": {
                    "theme_name": "paper-dark",
                    "language": "zh-CN",
                    "layout_grammar": "headline-plus-evidence",
                },
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "method",
                        "narrative_goal": "解释架构",
                        "content_focus": "method_components",
                        "visual_strategy": "text_only",
                        "candidate_assets": [],
                        "animation_intent": "soft_intro",
                    }
                ],
            },
            scene_builder=lambda presentation_plan, **kwargs: seen.update(
                {"scene_style_guide": kwargs.get("deck_style_guide")}
            ) or [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": "解释架构",
                    "summary_line": "解释架构",
                    "layout_strategy": "hero-text",
                    "content_blocks": [{"type": "bullets", "items": ["a"]}],
                    "citations": [{"page_no": 1, "block_ids": ["b1"]}],
                    "asset_bindings": [],
                    "animation_plan": {"type": "soft_intro"},
                    "speaker_note_seed": "paper-dark",
                }
            ],
            html_renderer=lambda scene_spec, **kwargs: seen.update(
                {"html_style_guide": kwargs.get("deck_style_guide")}
            ) or {
                "page_id": scene_spec["page_id"],
                "html": f"<section>{scene_spec['title']}</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {"theme_name": kwargs.get("deck_style_guide", {}).get("theme_name", "")},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(seen["scene_style_guide"]["theme_name"], "paper-dark")
        self.assertEqual(seen["html_style_guide"]["layout_grammar"], "headline-plus-evidence")
        self.assertEqual(result["rendered_slide_pages"][0]["render_meta"]["theme_name"], "paper-dark")

    def test_generate_asset_slides_runtime_bundle_isolates_parallel_scene_and_html_failures_by_page(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="not_generated")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="pending",
            runtime_bundle=None,
            analysis_pack=None,
            visual_asset_catalog=None,
            presentation_plan=None,
            scene_specs=None,
            rendered_slide_pages=None,
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "problem_statements": ["Recurrence slows training."],
                "method_components": ["Self-attention encoder-decoder."],
                "main_results": ["Better BLEU with less training cost."],
            },
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda *_args, **_kwargs: {
                "page_count": 2,
                "deck_style_guide": {"theme_name": "paper-dark", "language": "zh-CN"},
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "cover",
                        "narrative_goal": "第一页",
                        "content_focus": "problem",
                        "visual_strategy": "text_only",
                        "candidate_assets": [],
                        "animation_intent": "soft_intro",
                    },
                    {
                        "page_id": "page-2",
                        "scene_role": "method",
                        "narrative_goal": "第二页",
                        "content_focus": "method",
                        "visual_strategy": "text_only",
                        "candidate_assets": [],
                        "animation_intent": "soft_intro",
                    },
                ],
            },
            scene_builder=lambda presentation_plan, **kwargs: [
                {
                    "page_id": page["page_id"],
                    "title": page["narrative_goal"],
                    "summary_line": page["narrative_goal"],
                    "layout_strategy": "hero-text",
                    "content_blocks": [{"type": "bullets", "items": [page["page_id"]]}],
                    "citations": [{"page_no": 1, "block_ids": [page["page_id"]]}],
                    "asset_bindings": [],
                    "animation_plan": {"type": "soft_intro"},
                    "speaker_note_seed": kwargs.get("deck_style_guide", {}).get("theme_name", ""),
                }
                if page["page_id"] == "page-1"
                else (_ for _ in ()).throw(RuntimeError("scene page-2 failed"))
                for page in presentation_plan["pages"]
            ],
            batch_html_renderer=lambda *_args, **_kwargs: {
                "deck_meta": {"theme_name": "paper-dark"},
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>第一页</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {"theme_name": "paper-dark"},
                    },
                    {
                        "page_id": "page-2",
                        "html": "<section class=\"slide-page\"><h1>第二页</h1><p>第二页</p></section>",
                        "css": ".slide-page{width:100%;height:100%;box-sizing:border-box;padding:72px 88px;background:#fff;color:#1f2937;font-family:Inter,system-ui,sans-serif;}.slide-page h1{margin:0 0 24px;font-size:42px;line-height:1.1;}.slide-page p{margin:0;font-size:24px;line-height:1.5;}",
                        "asset_refs": [],
                        "render_meta": {"layout_strategy": "hero-text"},
                    },
                ],
                "html_meta": [
                    {"page_id": "page-1", "status": "success", "reason": ""},
                    {"page_id": "page-2", "status": "fallback", "reason": "html page-2 failed"},
                ],
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual([scene["page_id"] for scene in result["scene_specs"]], ["page-1", "page-2"])
        self.assertEqual(result["error_meta"]["scene_generation"][0]["status"], "success")
        self.assertEqual(result["error_meta"]["scene_generation"][1]["status"], "fallback")
        self.assertEqual(result["error_meta"]["html_generation"][0]["status"], "success")
        self.assertEqual(result["error_meta"]["html_generation"][1]["status"], "fallback")

    def test_generate_asset_slides_runtime_bundle_rebuilds_scene_stage_for_target_pages(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={
                "page_count": 3,
                "pages": [
                    {"page_id": "page-1", "html": "<section>old-1</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
                    {"page_id": "page-2", "html": "<section>old-2</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
                    {"page_id": "page-3", "html": "<section>old-3</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
                ],
            },
            analysis_pack={"problem_statements": ["Persisted analysis"]},
            visual_asset_catalog=[{"asset_id": "fig-1"}],
            presentation_plan={
                "page_count": 3,
                "pages": [
                    {"page_id": "page-1", "narrative_goal": "Page 1", "candidate_assets": []},
                    {"page_id": "page-2", "narrative_goal": "Page 2", "candidate_assets": []},
                    {"page_id": "page-3", "narrative_goal": "Page 3", "candidate_assets": []},
                ],
            },
            scene_specs=[
                {"page_id": "page-1", "title": "Old 1", "summary_line": "Old 1", "layout_strategy": "hero-text"},
                {"page_id": "page-2", "title": "Old 2", "summary_line": "Old 2", "layout_strategy": "hero-text"},
                {"page_id": "page-3", "title": "Old 3", "summary_line": "Old 3", "layout_strategy": "hero-text"},
            ],
            rendered_slide_pages=[
                {"page_id": "page-1", "html": "<section>old-1</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>old-2</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-3", "html": "<section>old-3</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}},
            ],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        scene_calls: list[str] = []
        html_calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="scene",
            page_numbers=[2],
            reuse_analysis_pack=True,
            reuse_presentation_plan=True,
            analysis_builder=lambda *_args, **_kwargs: self.fail("analysis should be reused"),
            plan_builder=lambda *_args, **_kwargs: self.fail("plan should be reused"),
            scene_builder=lambda presentation_plan, **_kwargs: scene_calls.append(presentation_plan["pages"][0]["page_id"]) or [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": "Rebuilt 2",
                    "summary_line": "Rebuilt 2",
                    "layout_strategy": "hero-text",
                }
            ],
            html_renderer=lambda scene_spec, **_kwargs: html_calls.append(scene_spec["page_id"]) or {
                "page_id": scene_spec["page_id"],
                "html": f"<section>{scene_spec['title']}</section>",
                "css": (
                    "html, body { width: 1600px; height: 900px; overflow: hidden; }"
                    ".slide-canvas { width: 1600px; height: 900px; overflow: hidden; }"
                ),
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(scene_calls, ["page-2"])
        self.assertEqual(html_calls, ["page-2"])
        self.assertEqual([item["title"] for item in result["scene_specs"]], ["Old 1", "Rebuilt 2", "Old 3"])
        self.assertEqual(
            [item["html"] for item in result["rendered_slide_pages"]],
            ["<section>old-1</section>", "<section>Rebuilt 2</section>", "<section>old-3</section>"],
        )
        self.assertEqual(result["runtime_bundle"]["page_count"], 3)
        self.assertEqual(result["slides_status"], "ready")
        self.assertEqual(result["error_meta"]["rebuild_meta"]["effective_page_numbers"], [2])
        self.assertEqual(
            result["error_meta"]["rebuild_meta"]["reused_layers"],
            ["analysis_pack", "visual_asset_catalog", "presentation_plan"],
        )
        self.assertEqual(
            result["error_meta"]["rebuild_meta"]["rebuilt_layers"],
            ["scene_specs", "rendered_slide_pages", "runtime_bundle"],
        )
        self.assertEqual(result["error_meta"]["plan_generation"][0]["status"], "reused")

    def test_generate_asset_slides_runtime_bundle_rebuilds_html_stage_for_target_pages(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={
                "page_count": 3,
                "pages": [
                    {"page_id": "page-1", "html": "<section>old-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                    {"page_id": "page-2", "html": "<section>old-2</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                    {"page_id": "page-3", "html": "<section>old-3</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                ],
            },
            analysis_pack={"problem_statements": ["Persisted analysis"]},
            visual_asset_catalog=[{"asset_id": "fig-1"}],
            presentation_plan={
                "page_count": 3,
                "pages": [
                    {"page_id": "page-1", "narrative_goal": "Page 1", "candidate_assets": []},
                    {"page_id": "page-2", "narrative_goal": "Page 2", "candidate_assets": []},
                    {"page_id": "page-3", "narrative_goal": "Page 3", "candidate_assets": []},
                ],
            },
            scene_specs=[
                {"page_id": "page-1", "title": "Scene 1", "summary_line": "Scene 1", "layout_strategy": "hero-text"},
                {"page_id": "page-2", "title": "Scene 2", "summary_line": "Scene 2", "layout_strategy": "hero-text"},
                {"page_id": "page-3", "title": "Scene 3", "summary_line": "Scene 3", "layout_strategy": "hero-text"},
            ],
            rendered_slide_pages=[
                {"page_id": "page-1", "html": "<section>old-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>old-2</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-3", "html": "<section>old-3</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
            ],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        html_calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="html",
            page_numbers=[3],
            analysis_builder=lambda *_args, **_kwargs: self.fail("analysis should not run for html rebuild"),
            plan_builder=lambda *_args, **_kwargs: self.fail("plan should not run for html rebuild"),
            scene_builder=lambda *_args, **_kwargs: self.fail("scene should not run for html rebuild"),
            html_renderer=lambda scene_spec, **_kwargs: html_calls.append(scene_spec["page_id"]) or {
                "page_id": scene_spec["page_id"],
                "html": f"<section>updated-{scene_spec['page_id']}</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(html_calls, ["page-3"])
        self.assertEqual(result["scene_specs"], presentation.scene_specs)
        self.assertEqual(
            [item["html"] for item in result["rendered_slide_pages"]],
            ["<section>old-1</section>", "<section>old-2</section>", "<section>updated-page-3</section>"],
        )
        self.assertIn("scene_specs", result["error_meta"]["rebuild_meta"]["reused_layers"])
        self.assertEqual(
            result["error_meta"]["rebuild_meta"]["rebuilt_layers"],
            ["rendered_slide_pages", "runtime_bundle"],
        )
        self.assertEqual(result["error_meta"]["rebuild_meta"]["effective_page_numbers"], [3])

    def test_generate_asset_slides_runtime_bundle_prioritizes_explicit_page_numbers_over_failed_only(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={
                "page_count": 3,
                "pages": [
                    {"page_id": "page-1", "html": "<section>old-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                    {
                        "page_id": "page-2",
                        "html": "<section>old-2</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {
                            "validation": {"status": "failed", "blocking": True, "reason": "overflow_detected"},
                            "runtime_gate_status": "failed",
                        },
                    },
                    {"page_id": "page-3", "html": "<section>old-3</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                ],
                "failed_page_numbers": [2],
            },
            analysis_pack={"problem_statements": ["Persisted analysis"]},
            visual_asset_catalog=[{"asset_id": "fig-1"}],
            presentation_plan={
                "page_count": 3,
                "pages": [
                    {"page_id": "page-1", "narrative_goal": "Page 1", "candidate_assets": []},
                    {"page_id": "page-2", "narrative_goal": "Page 2", "candidate_assets": []},
                    {"page_id": "page-3", "narrative_goal": "Page 3", "candidate_assets": []},
                ],
            },
            scene_specs=[
                {"page_id": "page-1", "title": "Scene 1", "summary_line": "Scene 1", "layout_strategy": "hero-text"},
                {"page_id": "page-2", "title": "Scene 2", "summary_line": "Scene 2", "layout_strategy": "hero-text"},
                {"page_id": "page-3", "title": "Scene 3", "summary_line": "Scene 3", "layout_strategy": "hero-text"},
            ],
            rendered_slide_pages=[
                {"page_id": "page-1", "html": "<section>old-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>old-2</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-3", "html": "<section>old-3</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
            ],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        html_calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="html",
            page_numbers=[3],
            failed_only=True,
            analysis_builder=lambda *_args, **_kwargs: self.fail("analysis should not run for html rebuild"),
            plan_builder=lambda *_args, **_kwargs: self.fail("plan should not run for html rebuild"),
            scene_builder=lambda *_args, **_kwargs: self.fail("scene should not run for html rebuild"),
            html_renderer=lambda scene_spec, **_kwargs: html_calls.append(scene_spec["page_id"]) or {
                "page_id": scene_spec["page_id"],
                "html": f"<section>updated-{scene_spec['page_id']}</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(html_calls, ["page-3"])
        self.assertEqual(result["error_meta"]["rebuild_meta"]["effective_page_numbers"], [3])
        self.assertEqual(result["error_meta"]["rebuild_meta"]["requested_page_numbers"], [3])

    def test_generate_asset_slides_runtime_bundle_rebuilds_runtime_stage_from_persisted_pages(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={"page_count": 1, "pages": [{"page_id": "page-1", "html": "<section>old</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}}]},
            analysis_pack={"problem_statements": ["Persisted analysis"]},
            visual_asset_catalog=[{"asset_id": "fig-1"}],
            presentation_plan={"page_count": 1, "pages": [{"page_id": "page-1", "narrative_goal": "Page 1", "candidate_assets": []}]},
            scene_specs=[{"page_id": "page-1", "title": "Scene 1", "summary_line": "Scene 1", "layout_strategy": "hero-text"}],
            rendered_slide_pages=[{"page_id": "page-1", "html": "<section>persisted</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }.slide-canvas { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}}],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        runtime_calls: list[list[str]] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="runtime",
            analysis_builder=lambda *_args, **_kwargs: self.fail("analysis should not run for runtime rebuild"),
            plan_builder=lambda *_args, **_kwargs: self.fail("plan should not run for runtime rebuild"),
            scene_builder=lambda *_args, **_kwargs: self.fail("scene should not run for runtime rebuild"),
            html_renderer=lambda *_args, **_kwargs: self.fail("html should not run for runtime rebuild"),
            runtime_bundle_builder=lambda rendered_pages: runtime_calls.append([page["page_id"] for page in rendered_pages]) or {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(runtime_calls, [["page-1"]])
        self.assertEqual(result["rendered_slide_pages"][0]["html"], "<section>persisted</section>")
        self.assertIn("rendered_slide_pages", result["error_meta"]["rebuild_meta"]["reused_layers"])
        self.assertEqual(result["error_meta"]["rebuild_meta"]["rebuilt_layers"], ["runtime_bundle"])
        self.assertEqual(result["slides_status"], "ready")

    def test_generate_asset_slides_runtime_bundle_skips_failed_only_rebuild_when_no_failed_pages(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="ready")
        persisted_runtime_bundle = {
            "page_count": 2,
            "pages": [
                {"page_id": "page-1", "html": "<section>ok-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>ok-2</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
            ],
        }
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle=persisted_runtime_bundle,
            analysis_pack={"problem_statements": ["Persisted analysis"]},
            visual_asset_catalog=[{"asset_id": "fig-1"}],
            presentation_plan={
                "page_count": 2,
                "pages": [
                    {"page_id": "page-1", "narrative_goal": "Page 1", "candidate_assets": []},
                    {"page_id": "page-2", "narrative_goal": "Page 2", "candidate_assets": []},
                ],
            },
            scene_specs=[
                {"page_id": "page-1", "title": "Scene 1", "summary_line": "Scene 1", "layout_strategy": "hero-text"},
                {"page_id": "page-2", "title": "Scene 2", "summary_line": "Scene 2", "layout_strategy": "hero-text"},
            ],
            rendered_slide_pages=[
                {"page_id": "page-1", "html": "<section>ok-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>ok-2</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
            ],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="html",
            failed_only=True,
            analysis_builder=lambda *_args, **_kwargs: self.fail("analysis should not run when failed_only has no targets"),
            plan_builder=lambda *_args, **_kwargs: self.fail("plan should not run when failed_only has no targets"),
            scene_builder=lambda *_args, **_kwargs: self.fail("scene should not run when failed_only has no targets"),
            html_renderer=lambda *_args, **_kwargs: self.fail("html should not run when failed_only has no targets"),
            runtime_bundle_builder=lambda *_args, **_kwargs: self.fail("runtime should not rebuild when failed_only has no targets"),
        )

        self.assertEqual(result["runtime_bundle"]["page_count"], persisted_runtime_bundle["page_count"])
        self.assertEqual(result["runtime_bundle"]["pages"], persisted_runtime_bundle["pages"])
        self.assertEqual(result["slides_status"], "ready")
        self.assertEqual(result["error_meta"]["rebuild_meta"]["effective_page_numbers"], [])
        self.assertIn("runtime_bundle", result["error_meta"]["rebuild_meta"]["reused_layers"])
        self.assertEqual(result["error_meta"]["rebuild_meta"]["rebuilt_layers"], [])

    def test_generate_asset_slides_runtime_bundle_rebuilds_only_failed_pages_when_failed_only_enabled(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="failed")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="failed",
            runtime_bundle={
                "page_count": 4,
                "pages": [
                    {"page_id": "page-1", "html": "<section>ok-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                    {
                        "page_id": "page-2",
                        "html": "<section>bad-2</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {
                            "validation": {"status": "failed", "blocking": True, "reason": "overflow_detected"},
                            "runtime_gate_status": "failed",
                        },
                    },
                    {"page_id": "page-3", "html": "<section>ok-3</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                    {"page_id": "page-4", "html": "<section>ok-4</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                ],
                "failed_page_numbers": [2],
            },
            analysis_pack={"problem_statements": ["Persisted analysis"]},
            visual_asset_catalog=[{"asset_id": "fig-1"}],
            presentation_plan={
                "page_count": 4,
                "pages": [
                    {"page_id": "page-1", "narrative_goal": "Page 1", "candidate_assets": []},
                    {"page_id": "page-2", "narrative_goal": "Page 2", "candidate_assets": []},
                    {"page_id": "page-3", "narrative_goal": "Page 3", "candidate_assets": []},
                    {"page_id": "page-4", "narrative_goal": "Page 4", "candidate_assets": []},
                ],
            },
            scene_specs=[
                {"page_id": "page-1", "title": "Scene 1", "summary_line": "Scene 1", "layout_strategy": "hero-text"},
                {"page_id": "page-2", "title": "Scene 2", "summary_line": "Scene 2", "layout_strategy": "hero-text"},
                {"page_id": "page-3", "title": "Scene 3", "summary_line": "Scene 3", "layout_strategy": "hero-text"},
                {"page_id": "page-4", "title": "Scene 4", "summary_line": "Scene 4", "layout_strategy": "hero-text"},
            ],
            rendered_slide_pages=[
                {"page_id": "page-1", "html": "<section>ok-1</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-2", "html": "<section>bad-2</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-3", "html": "<section>ok-3</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
                {"page_id": "page-4", "html": "<section>ok-4</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
            ],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )
        html_calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="html",
            failed_only=True,
            analysis_builder=lambda *_args, **_kwargs: self.fail("analysis should not run for html rebuild"),
            plan_builder=lambda *_args, **_kwargs: self.fail("plan should not run for html rebuild"),
            scene_builder=lambda *_args, **_kwargs: self.fail("scene should not run for html rebuild"),
            html_renderer=lambda scene_spec, **_kwargs: html_calls.append(scene_spec["page_id"]) or {
                "page_id": scene_spec["page_id"],
                "html": f"<section>updated-{scene_spec['page_id']}</section>",
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(html_calls, ["page-2"])
        self.assertEqual(result["error_meta"]["rebuild_meta"]["effective_page_numbers"], [2])
        self.assertEqual(
            [item["html"] for item in result["rendered_slide_pages"]],
            ["<section>ok-1</section>", "<section>updated-page-2</section>", "<section>ok-3</section>", "<section>ok-4</section>"],
        )

    def test_generate_asset_slides_runtime_bundle_rejects_invalid_stage_inputs(self) -> None:
        asset = SimpleNamespace(id="asset-1", title="Attention Is All You Need", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="ready",
            runtime_bundle={},
            analysis_pack={},
            visual_asset_catalog=[],
            presentation_plan={},
            scene_specs=[],
            rendered_slide_pages=[],
            error_meta={},
            tts_manifest={},
            playback_plan={},
        )

        with self.assertRaisesRegex(ValueError, "page_numbers is only supported"):
            generate_asset_slides_runtime_bundle(
                _FakeDb(asset, presentation),
                asset_id="asset-1",
                from_stage="runtime",
                page_numbers=[1],
            )

        with self.assertRaisesRegex(ValueError, "debug_target=html is not supported"):
            generate_asset_slides_runtime_bundle(
                _FakeDb(asset, presentation),
                asset_id="asset-1",
                from_stage="runtime",
                debug_target="html",
            )
