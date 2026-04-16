import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.document_chunk import AssetRetrievalSearchResponse
from app.schemas.document_chunk import RetrievalSearchHit
from app.services.slide_generation_v2_service import generate_asset_slides_runtime_bundle
from app.services.slide_planning_service import build_presentation_plan


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

    def commit(self):
        self.asset_status_history.append(getattr(self._asset, "slides_status", ""))
        super().commit()


class _StrictJsonDb(_FakeDb):
    def commit(self):
        import json

        json.dumps(self._presentation.analysis_pack)
        super().commit()


class SlideGenerationV2ServiceTests(unittest.TestCase):
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
                "css": ".page{}",
                "asset_refs": [],
                "render_meta": {},
            },
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertGreaterEqual(len(db.asset_status_history), 2)
        self.assertEqual(db.asset_status_history[0], "processing")
        self.assertEqual(db.asset_status_history[-1], "ready")

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
        self.assertEqual(result["error_meta"]["debug_target"], "plan")

    def test_generate_asset_slides_runtime_bundle_persists_new_pipeline_artifacts(self) -> None:
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
        parsed_payload = {
            "blocks": [
                {"block_id": "blk-1", "text": "Transformers rely entirely on attention.", "page_no": 1},
                {"block_id": "blk-fig-1", "text": "", "page_no": 2},
            ],
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
        }

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload=parsed_payload,
            analysis_builder=lambda *_args, **_kwargs: {
                "core_claims": ["Transformers remove recurrence."],
                "main_results": ["State-of-the-art BLEU on WMT14 En-De."],
            },
            visual_asset_builder=lambda assets, **_kwargs: [
                {
                    "asset_id": assets[0]["resource_id"],
                    "recommended_usage": "method_overview",
                    "page_no": 2,
                    "block_id": "blk-fig-1",
                }
            ],
            plan_builder=lambda analysis_pack, visual_asset_catalog, **_kwargs: {
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "scene_role": "method",
                        "narrative_goal": analysis_pack["core_claims"][0],
                        "candidate_assets": [visual_asset_catalog[0]["asset_id"]],
                    }
                ],
            },
            scene_builder=lambda presentation_plan, **_kwargs: [
                {
                    "page_id": presentation_plan["pages"][0]["page_id"],
                    "title": "Transformer Architecture",
                    "summary_line": "Self-attention replaces recurrence.",
                    "layout_strategy": "hero-visual-right",
                    "asset_bindings": [{"asset_id": "fig-1"}],
                }
            ],
            html_renderer=lambda scene_spec, **_kwargs: {
                "page_id": scene_spec["page_id"],
                "html": f"<section><h1>{scene_spec['title']}</h1></section>",
                "css": ".page{}",
                "asset_refs": scene_spec.get("asset_bindings", []),
                "render_meta": {"layout_strategy": scene_spec.get("layout_strategy", "")},
            },
            runtime_bundle_builder=lambda rendered_pages: {
                "page_count": len(rendered_pages),
                "pages": rendered_pages,
            },
        )

        self.assertEqual(result["asset_id"], "asset-1")
        self.assertEqual(result["slides_status"], "ready")
        self.assertEqual(result["runtime_bundle"]["page_count"], 1)
        self.assertEqual(result["presentation_plan"]["pages"][0]["page_id"], "page-1")
        self.assertEqual(result["scene_specs"][0]["title"], "Transformer Architecture")
        self.assertEqual(result["rendered_slide_pages"][0]["page_id"], "page-1")

    def test_generate_asset_slides_runtime_bundle_loads_parsed_payload_when_missing(self) -> None:
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
        load_calls: list[str] = []

        result = generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload=None,
            parsed_payload_loader=lambda _db, loaded_asset_id: {
                load_calls.append(loaded_asset_id) or loaded_asset_id: loaded_asset_id,
                "blocks": [
                    {"block_id": "blk-1", "text": "Transformers rely entirely on attention.", "page_no": 1}
                ],
                "assets": {"images": [], "tables": []},
            },
            analysis_builder=lambda *_args, **_kwargs: {
                "core_claims": ["Transformers remove recurrence."],
                "main_results": ["State-of-the-art BLEU on WMT14 En-De."],
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

        self.assertEqual(load_calls, ["asset-1"])
        self.assertEqual(result["runtime_bundle"]["page_count"], 1)

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
            return AssetRetrievalSearchResponse(
                asset_id=asset_id,
                query=query,
                top_k=top_k,
                results=[
                    RetrievalSearchHit(
                        chunk_id=f"hit-{query}",
                        score=0.9,
                        text="The model improves translation quality over strong baselines.",
                        page_start=8,
                        page_end=8,
                        block_ids=["block-1"],
                        section_path=["Results"],
                        quote_text="The model improves translation quality over strong baselines.",
                    )
                ],
            )

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

    def test_generate_asset_slides_runtime_bundle_default_analysis_builder_keeps_structured_fields(self) -> None:
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

        def _search(db, asset_id: str, query: str, top_k: int, rewrite_query: bool, strategy: str):  # noqa: ANN001
            family_to_text = {
                "research problem and motivation": ("c-problem", "Recurrence slows training on long sequences.", ["Introduction"]),
                "method overview and framework": ("c-method", "The Transformer uses self-attention instead of recurrence.", ["Model Architecture"]),
                "main experiment results performance": ("c-result", "Transformer improves BLEU on WMT14 En-De.", ["Results"]),
            }
            chunk_id, text, section_path = family_to_text.get(query, (f"hit-{query}", "Useful evidence.", ["Appendix"]))
            return AssetRetrievalSearchResponse(
                asset_id=asset_id,
                query=query,
                top_k=top_k,
                results=[
                    RetrievalSearchHit(
                        chunk_id=chunk_id,
                        score=0.9,
                        text=text,
                        page_start=1,
                        page_end=1,
                        block_ids=["block-1"],
                        section_path=section_path,
                        quote_text=text,
                    )
                ],
            )

        captured_analysis_pack: dict[str, object] = {}

        generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            parsed_payload={
                "blocks": [{"block_id": "blk-1", "text": "Intro", "page_no": 1}],
                "assets": {"images": [], "tables": []},
            },
            search_func=_search,
            visual_asset_builder=lambda *_args, **_kwargs: [],
            plan_builder=lambda analysis_pack, *_args, **_kwargs: captured_analysis_pack.update(analysis_pack) or {
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

        self.assertEqual(captured_analysis_pack["problem_statements"][0], "Recurrence slows training on long sequences.")
        self.assertEqual(captured_analysis_pack["method_components"][0], "The Transformer uses self-attention instead of recurrence.")
        self.assertEqual(captured_analysis_pack["main_results"][0], "Transformer improves BLEU on WMT14 En-De.")

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

    def test_generate_asset_slides_runtime_bundle_uses_llm_builders_when_enabled(self) -> None:
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
                "css": ".page{}",
                "asset_refs": scene_spec.get("asset_bindings", []),
                "render_meta": {"mode": "llm"},
            },
            plan_builder=lambda *_args, **_kwargs: self.fail("template plan builder should not run"),
            scene_builder=lambda *_args, **_kwargs: self.fail("template scene builder should not run"),
            html_renderer=lambda *_args, **_kwargs: self.fail("template html renderer should not run"),
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(calls, ["plan", "scene", "html"])
        self.assertEqual(result["runtime_bundle"]["pages"][0]["render_meta"]["mode"], "llm")

    def test_generate_asset_slides_runtime_bundle_serializes_analysis_pack_for_json_storage(self) -> None:
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
            html_renderer=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("html boom")),
            runtime_bundle_builder=lambda rendered_pages: {"page_count": len(rendered_pages), "pages": rendered_pages},
        )

        self.assertEqual(result["scene_specs"][0]["title"], "Recurrence slows training.")
        self.assertEqual(result["runtime_bundle"]["page_count"], 4)
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


if __name__ == "__main__":
    unittest.main()
