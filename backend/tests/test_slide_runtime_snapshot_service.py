import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_dsl_service import get_asset_slides_snapshot


class _ScalarResult:
    def __init__(self, obj):
        self.obj = obj

    def first(self):
        return self.obj


class _FakeDb:
    def __init__(self, asset, presentation):
        self._asset = asset
        self._presentation = presentation

    def get(self, model, asset_id):  # noqa: ANN001
        return self._asset if asset_id == self._asset.id else None

    def scalars(self, _statement):  # noqa: ANN001
        return _ScalarResult(self._presentation)


class SlideRuntimeSnapshotServiceTests(unittest.TestCase):
    def test_get_asset_slides_snapshot_marks_active_run_token_as_rebuilding(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="processing")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="processing",
            active_run_token="task-123",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>Hello</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {"layout_strategy": "hero"},
                    }
                ],
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
            error_meta={
                "rebuild_meta": {
                    "from_stage": "html",
                    "requested_page_numbers": [1],
                    "effective_page_numbers": [],
                    "failed_only": False,
                    "reused_layers": [],
                    "rebuilt_layers": [],
                }
            },
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertTrue(snapshot.rebuilding)
        self.assertEqual(snapshot.rebuild_reason, "runtime_bundle_rebuild")
        self.assertEqual(snapshot.slides_status, "processing")

    def test_get_asset_slides_snapshot_does_not_mark_failed_run_as_rebuilding(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="failed")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="failed",
            active_run_token=None,
            slides_dsl=None,
            runtime_bundle={"page_count": 0, "pages": []},
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
            error_meta={
                "worker_failure": {"message": "boom"},
                "rebuild_meta": {
                    "from_stage": "full",
                    "requested_page_numbers": [],
                    "effective_page_numbers": [],
                    "failed_only": False,
                    "reused_layers": [],
                    "rebuilt_layers": [],
                },
            },
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertFalse(snapshot.rebuilding)
        self.assertIsNone(snapshot.rebuild_reason)

    def test_get_asset_slides_snapshot_prefers_page_level_runtime_state_over_stale_summary(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 2,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>Hello</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {
                            "layout_strategy": "hero",
                            "validation": {"status": "passed", "blocking": False, "reason": None},
                            "runtime_gate_status": "ready",
                        },
                    },
                    {
                        "page_id": "page-2",
                        "html": "<section>World</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {
                            "layout_strategy": "hero",
                            "validation": {"status": "passed", "blocking": False, "reason": None},
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
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertEqual(snapshot.playback_status, "ready")
        self.assertEqual(snapshot.playable_page_count, 2)
        self.assertEqual(snapshot.failed_page_numbers, [])
        self.assertEqual(snapshot.runtime_bundle.validation_summary.status, "ready")
        self.assertTrue(snapshot.auto_page_supported)

    def test_get_asset_slides_snapshot_prefers_runtime_bundle_payload(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>Hello</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {"layout_strategy": "hero"},
                    }
                ],
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertIsNotNone(snapshot.runtime_bundle)
        self.assertEqual(snapshot.runtime_bundle.page_count, 1)
        self.assertEqual(snapshot.runtime_bundle.playable_page_count, 1)
        self.assertEqual(snapshot.runtime_bundle.failed_page_numbers, [])
        self.assertEqual(snapshot.runtime_bundle.pages[0].page_id, "page-1")
        self.assertIsNone(snapshot.slides_dsl)
        self.assertEqual(snapshot.playback_status, "ready")
        self.assertEqual(snapshot.playable_page_count, 1)
        self.assertEqual(snapshot.failed_page_numbers, [])
        self.assertTrue(snapshot.auto_page_supported)

    def test_get_asset_slides_snapshot_marks_empty_runtime_bundle_not_ready(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="ready")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 0,
                "pages": [],
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertEqual(snapshot.playback_status, "not_ready")
        self.assertEqual(snapshot.playable_page_count, 0)
        self.assertEqual(snapshot.failed_page_numbers, [])
        self.assertFalse(snapshot.auto_page_supported)

    def test_get_asset_slides_snapshot_marks_blocked_runtime_bundle_not_ready(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="failed")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>Hello</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {
                            "layout_strategy": "hero",
                            "validation": {"status": "failed", "reason": "overflow"},
                        },
                    }
                ],
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertEqual(snapshot.playback_status, "not_ready")
        self.assertEqual(snapshot.playable_page_count, 0)
        self.assertEqual(snapshot.failed_page_numbers, [1])
        self.assertEqual(snapshot.runtime_bundle.validation_summary.status, "not_ready")
        self.assertFalse(snapshot.auto_page_supported)
    def test_get_asset_slides_snapshot_marks_partially_failed_runtime_bundle_as_partial_ready(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="failed")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 2,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>Hello</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {"layout_strategy": "hero"},
                    },
                    {
                        "page_id": "page-2",
                        "html": "<section>World</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {
                            "layout_strategy": "hero",
                            "validation": {"status": "failed", "reason": "overflow"},
                        },
                    },
                ],
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertEqual(snapshot.playback_status, "partial_ready")
        self.assertEqual(snapshot.playable_page_count, 1)
        self.assertEqual(snapshot.failed_page_numbers, [2])
        self.assertEqual(snapshot.runtime_bundle.validation_summary.status, "partial_ready")
        self.assertTrue(snapshot.auto_page_supported)
    def test_get_asset_slides_snapshot_exposes_rebuild_meta(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="processing")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            slides_dsl=None,
            runtime_bundle={
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "page-1",
                        "html": "<section>Hello</section>",
                        "css": ".page{}",
                        "asset_refs": [],
                        "render_meta": {"layout_strategy": "hero"},
                    }
                ],
            },
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
            error_meta={
                "rebuild_meta": {
                    "from_stage": "html",
                    "requested_page_numbers": [2, 3],
                    "effective_page_numbers": [2],
                    "failed_only": True,
                    "reused_layers": ["scene_specs"],
                    "rebuilt_layers": ["rendered_slide_pages", "runtime_bundle"],
                }
            },
        )

        snapshot = get_asset_slides_snapshot(_FakeDb(asset, presentation), "asset-1")

        self.assertIsNotNone(snapshot.rebuild_meta)
        self.assertEqual(snapshot.rebuild_meta.from_stage, "html")
        self.assertEqual(snapshot.rebuild_meta.requested_page_numbers, [2, 3])
        self.assertEqual(snapshot.rebuild_meta.effective_page_numbers, [2])
        self.assertTrue(snapshot.rebuild_meta.failed_only)
        self.assertEqual(snapshot.rebuild_meta.reused_layers, ["scene_specs"])
        self.assertEqual(
            snapshot.rebuild_meta.rebuilt_layers,
            ["rendered_slide_pages", "runtime_bundle"],
        )


if __name__ == "__main__":
    unittest.main()
