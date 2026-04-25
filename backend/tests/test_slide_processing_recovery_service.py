import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.asset_service import get_asset_detail
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
        self.commit_count = 0

    def get(self, model, asset_id):  # noqa: ANN001
        return self._asset if asset_id == self._asset.id else None

    def scalars(self, _statement):  # noqa: ANN001
        return _ScalarResult(self._presentation)

    def commit(self):
        self.commit_count += 1

    def refresh(self, _obj):  # noqa: ANN001
        return None


class SlideProcessingRecoveryServiceTests(unittest.TestCase):
    def test_get_asset_slides_snapshot_does_not_recover_processing_within_extended_timeout(self) -> None:
        stale_at = datetime.now(UTC) - timedelta(minutes=10)
        asset = SimpleNamespace(id="asset-1", slides_status="processing", updated_at=stale_at)
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="processing",
            slides_dsl=None,
            runtime_bundle={"page_count": 0, "pages": []},
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
            error_meta={},
            active_run_token="task-123",
            updated_at=stale_at,
        )
        db = _FakeDb(asset, presentation)

        snapshot = get_asset_slides_snapshot(db, "asset-1")

        self.assertEqual(snapshot.slides_status, "processing")
        self.assertTrue(snapshot.rebuilding)
        self.assertEqual(snapshot.rebuild_reason, "runtime_bundle_rebuild")
        self.assertEqual(asset.slides_status, "processing")
        self.assertEqual(presentation.status, "processing")
        self.assertEqual(db.commit_count, 0)

    def test_get_asset_slides_snapshot_recovers_stale_processing_status(self) -> None:
        stale_at = datetime.now(UTC) - timedelta(minutes=25)
        asset = SimpleNamespace(id="asset-1", slides_status="processing", updated_at=stale_at)
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="processing",
            slides_dsl=None,
            runtime_bundle={"page_count": 0, "pages": []},
            tts_manifest={},
            playback_plan={},
            dsl_quality_report={},
            dsl_fix_logs=[],
            error_meta={},
            active_run_token=None,
            updated_at=stale_at,
        )
        db = _FakeDb(asset, presentation)

        snapshot = get_asset_slides_snapshot(db, "asset-1")

        self.assertEqual(snapshot.slides_status, "failed")
        self.assertEqual(snapshot.rebuild_reason, "stale_processing_recovered")
        self.assertFalse(snapshot.rebuilding)
        self.assertEqual(asset.slides_status, "failed")
        self.assertEqual(presentation.status, "failed")
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(
            presentation.error_meta["stale_processing_recovery"]["reason"],
            "slides_processing_timeout",
        )

    def test_get_asset_detail_recovers_stale_processing_status(self) -> None:
        stale_at = datetime.now(UTC) - timedelta(minutes=25)
        asset = SimpleNamespace(
            id="asset-1",
            user_id="user-1",
            title="Retrieval-Augmented Generation",
            authors=[],
            abstract=None,
            source_type="upload",
            language="en",
            status="ready",
            parse_error_message=None,
            parse_status="ready",
            kb_status="ready",
            mindmap_status="ready",
            slides_status="processing",
            anki_status="not_generated",
            quiz_status="not_generated",
            created_at=stale_at,
            updated_at=stale_at,
        )
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="processing",
            runtime_bundle={"page_count": 0, "pages": []},
            error_meta={},
            active_run_token=None,
            updated_at=stale_at,
        )
        db = _FakeDb(asset, presentation)

        detail = get_asset_detail(db, "asset-1")

        self.assertIsNotNone(detail)
        self.assertEqual(detail.enhanced_resources.slides_status, "failed")
        self.assertEqual(asset.slides_status, "failed")
        self.assertEqual(presentation.status, "failed")
        self.assertEqual(db.commit_count, 1)
