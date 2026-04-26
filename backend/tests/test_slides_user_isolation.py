import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.slide_dsl_service import get_asset_slides_snapshot
from app.services.slide_generation_v2_service import enqueue_asset_slides_runtime_bundle_rebuild
from app.services.slide_tts_service import ensure_asset_slide_tts


class SlidesUserIsolationTests(unittest.TestCase):
    def test_get_asset_slides_snapshot_requires_current_user_asset(self) -> None:
        db = SimpleNamespace()

        with patch("app.services.slide_dsl_service.require_user_asset", side_effect=HTTPException(status_code=404, detail="未找到对应的学习资产。")):
            with self.assertRaises(HTTPException) as ctx:
                get_asset_slides_snapshot(db, "asset-1", "user-a")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_enqueue_asset_slides_runtime_bundle_rebuild_requires_current_user_asset(self) -> None:
        db = SimpleNamespace()

        with patch("app.services.slide_generation_v2_service.require_user_asset", side_effect=HTTPException(status_code=404, detail="未找到对应的学习资产。")):
            with self.assertRaises(HTTPException) as ctx:
                enqueue_asset_slides_runtime_bundle_rebuild(
                    db,
                    asset_id="asset-1",
                    user_id="user-a",
                    from_stage="full",
                    page_numbers=None,
                    failed_only=False,
                    reuse_analysis_pack=True,
                    reuse_presentation_plan=True,
                    debug_target="full",
                )

        self.assertEqual(ctx.exception.status_code, 404)

    def test_ensure_asset_slide_tts_requires_current_user_asset(self) -> None:
        db = SimpleNamespace()

        with patch("app.services.slide_tts_service.require_user_asset", side_effect=HTTPException(status_code=404, detail="未找到对应的学习资产。")):
            with self.assertRaises(HTTPException) as ctx:
                ensure_asset_slide_tts(db, "asset-1", "user-a", page_index=0, prefetch_next=True)

        self.assertEqual(ctx.exception.status_code, 404)
