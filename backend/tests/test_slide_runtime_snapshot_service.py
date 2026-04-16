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
        self.assertEqual(snapshot.runtime_bundle.pages[0].page_id, "page-1")
        self.assertIsNone(snapshot.slides_dsl)
        self.assertEqual(snapshot.playback_status, "ready")
        self.assertTrue(snapshot.auto_page_supported)


if __name__ == "__main__":
    unittest.main()
