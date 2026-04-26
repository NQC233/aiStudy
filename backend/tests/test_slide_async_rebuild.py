import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.routes.assets import rebuild_asset_runtime_bundle_slides_endpoint
from app.schemas.slide_dsl import AssetSlidesRebuildRequest
from app.schemas.slide_dsl import AssetSlidesResponse
from app.services.slide_generation_v2_service import (
    enqueue_asset_slides_runtime_bundle_rebuild,
)
from app.workers import tasks as worker_tasks


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
        self.rollback_count = 0

    def get(self, model, asset_id):  # noqa: ANN001
        return self._asset if asset_id == self._asset.id else None

    def scalars(self, _statement):  # noqa: ANN001
        return _ScalarResult(self._presentation)

    def add(self, obj):  # noqa: ANN001
        self._presentation = obj

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def refresh(self, _obj):  # noqa: ANN001
        return None

    def close(self):
        return None


class SlideAsyncRebuildTests(unittest.TestCase):
    def test_enqueue_asset_slides_runtime_bundle_rebuild_marks_processing_and_records_request(self) -> None:
        asset = SimpleNamespace(id="asset-1", user_id="user-1", slides_status="failed")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="failed",
            error_meta={},
            active_run_token=None,
            updated_at=None,
        )
        db = _FakeDb(asset, presentation)

        with patch(
            "app.services.slide_generation_v2_service.require_user_asset",
            return_value=asset,
        ):
            queued_asset, queued_presentation = enqueue_asset_slides_runtime_bundle_rebuild(
                db,
                asset_id="asset-1",
                user_id="user-1",
                from_stage="html",
                page_numbers=[3, 1, 3],
                failed_only=True,
                reuse_analysis_pack=True,
                reuse_presentation_plan=False,
                debug_target="full",
            )

        self.assertIs(queued_asset, asset)
        self.assertIs(queued_presentation, presentation)
        self.assertEqual(asset.slides_status, "processing")
        self.assertEqual(presentation.status, "processing")
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(
            presentation.error_meta["rebuild_meta"],
            {
                "from_stage": "html",
                "requested_page_numbers": [3, 1],
                "effective_page_numbers": [],
                "failed_only": True,
                "reused_layers": [],
                "rebuilt_layers": [],
            },
        )

    def test_enqueue_asset_slides_runtime_bundle_rebuild_rejects_active_processing(self) -> None:
        asset = SimpleNamespace(id="asset-1", user_id="user-1", slides_status="processing")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="processing",
            error_meta={},
            active_run_token="task-1",
            updated_at=None,
        )
        db = _FakeDb(asset, presentation)

        with patch(
            "app.services.slide_generation_v2_service.require_user_asset",
            return_value=asset,
        ):
            with self.assertRaises(HTTPException) as ctx:
                enqueue_asset_slides_runtime_bundle_rebuild(
                    db,
                    asset_id="asset-1",
                    user_id="user-1",
                    from_stage="full",
                    page_numbers=[],
                    failed_only=False,
                    reuse_analysis_pack=True,
                    reuse_presentation_plan=True,
                    debug_target="full",
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(str(ctx.exception.detail), "当前资产演示内容正在生成中。")

    def test_rebuild_asset_runtime_bundle_slides_endpoint_enqueues_celery_and_persists_task_id(self) -> None:
        asset = SimpleNamespace(id="asset-1", user_id="user-1", slides_status="failed")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="failed",
            error_meta={},
            active_run_token=None,
            updated_at=None,
        )
        db = _FakeDb(asset, presentation)
        snapshot = AssetSlidesResponse(asset_id="asset-1", slides_status="processing")
        current_user = SimpleNamespace(id="user-1")

        with (
            patch(
                "app.api.routes.assets.enqueue_asset_slides_runtime_bundle_rebuild",
                return_value=(asset, presentation),
            ) as enqueue_rebuild,
            patch(
                "app.api.routes.assets.enqueue_generate_asset_slides_runtime_bundle"
            ) as enqueue_task,
            patch(
                "app.api.routes.assets.get_asset_slides_snapshot",
                return_value=snapshot,
            ),
        ):
            enqueue_task.delay.return_value = SimpleNamespace(id="task-123")
            response = rebuild_asset_runtime_bundle_slides_endpoint(
                "asset-1",
                AssetSlidesRebuildRequest(from_stage="scene", page_numbers=[2]),
                db,
                current_user,
            )

        enqueue_rebuild.assert_called_once_with(
            db,
            asset_id="asset-1",
            user_id="user-1",
            from_stage="scene",
            page_numbers=[2],
            failed_only=False,
            reuse_analysis_pack=True,
            reuse_presentation_plan=True,
            debug_target="full",
        )
        enqueue_task.delay.assert_called_once_with(
            "asset-1",
            from_stage="scene",
            page_numbers=[2],
            failed_only=False,
            reuse_analysis_pack=True,
            reuse_presentation_plan=True,
            debug_target="full",
        )
        self.assertEqual(presentation.active_run_token, "task-123")
        self.assertEqual(response, snapshot)

    def test_enqueue_generate_asset_slides_runtime_bundle_marks_failed_on_worker_exception(self) -> None:
        asset = SimpleNamespace(id="asset-1", slides_status="processing")
        presentation = SimpleNamespace(
            asset_id="asset-1",
            status="processing",
            error_meta={},
            active_run_token="task-123",
            updated_at=None,
        )
        db = _FakeDb(asset, presentation)

        with patch.object(worker_tasks, "SessionLocal", return_value=db), patch.object(
            worker_tasks,
            "generate_asset_slides_runtime_bundle",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                worker_tasks.enqueue_generate_asset_slides_runtime_bundle.run(
                    "asset-1",
                    from_stage="full",
                    page_numbers=None,
                    failed_only=False,
                    reuse_analysis_pack=True,
                    reuse_presentation_plan=True,
                    debug_target="full",
                )

        self.assertEqual(asset.slides_status, "failed")
        self.assertEqual(presentation.status, "failed")
        self.assertIsNone(presentation.active_run_token)
        self.assertEqual(
            presentation.error_meta["worker_failure"]["message"],
            "boom",
        )
