import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.routes.assets import (
    create_asset_chat_session_endpoint,
    create_asset_note_endpoint,
    list_asset_endpoint,
    list_asset_notes_endpoint,
    upload_asset_endpoint,
)
from app.schemas.chat import ChatSessionCreateRequest
from app.schemas.note import CreateNoteRequest, NoteAnchorPayload
from app.services.asset_service import require_user_asset, seed_dev_user_and_assets


class _ScalarResult:
    def __init__(self, obj):
        self.obj = obj

    def first(self):
        return self.obj

    def all(self):
        return []


class AssetRouteUserPropagationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = SimpleNamespace()
        self.current_user = SimpleNamespace(id="user-123")

    def test_list_assets_passes_current_user_id(self) -> None:
        with patch("app.api.routes.assets.list_assets", return_value=[]) as list_assets_mock:
            result = list_asset_endpoint(db=self.db, current_user=self.current_user)

        self.assertEqual(result, [])
        list_assets_mock.assert_called_once_with(self.db, "user-123")

    def test_create_asset_chat_session_passes_current_user_id(self) -> None:
        payload = ChatSessionCreateRequest(title="Session")
        response = {"id": "session-1"}

        with patch("app.api.routes.assets.create_asset_chat_session", return_value=response) as create_mock:
            result = create_asset_chat_session_endpoint(
                asset_id="asset-1",
                payload=payload,
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        create_mock.assert_called_once_with(
            db=self.db,
            asset_id="asset-1",
            user_id="user-123",
            payload=payload,
        )

    def test_create_asset_note_passes_current_user_id(self) -> None:
        payload = CreateNoteRequest(
            anchor=NoteAnchorPayload(anchor_type="text_selection", page_no=1, selected_text="intro"),
            content="note body",
        )
        response = {"id": "note-1"}

        with patch("app.api.routes.assets.create_asset_note", return_value=response) as create_mock:
            result = create_asset_note_endpoint(
                asset_id="asset-1",
                payload=payload,
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        create_mock.assert_called_once_with(
            db=self.db,
            asset_id="asset-1",
            user_id="user-123",
            payload=payload,
        )

    def test_list_asset_notes_passes_current_user_id(self) -> None:
        response = {"asset_id": "asset-1", "total": 0, "notes": []}

        with patch("app.api.routes.assets.list_asset_notes", return_value=response) as list_notes_mock:
            result = list_asset_notes_endpoint(
                asset_id="asset-1",
                anchor_type=None,
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        list_notes_mock.assert_called_once_with(
            db=self.db,
            asset_id="asset-1",
            user_id="user-123",
            anchor_type=None,
        )

    async def test_upload_asset_passes_current_user_id(self) -> None:
        file = SimpleNamespace(
            filename="paper.pdf",
            content_type="application/pdf",
            read=AsyncMock(return_value=b"%PDF-1.4 fake"),
        )
        response = {"asset": {"id": "asset-1"}}

        with patch("app.api.routes.assets.validate_pdf_upload") as validate_mock, patch(
            "app.api.routes.assets.create_uploaded_asset",
            return_value=response,
        ) as create_mock:
            result = await upload_asset_endpoint(
                file=file,
                title="Paper",
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        validate_mock.assert_called_once()
        create_mock.assert_called_once_with(
            db=self.db,
            user_id="user-123",
            filename="paper.pdf",
            content_type="application/pdf",
            content=b"%PDF-1.4 fake",
            title="Paper",
        )


class AssetOwnerCheckTests(unittest.TestCase):
    def test_require_user_asset_rejects_other_users_asset(self) -> None:
        db = SimpleNamespace(scalars=lambda _statement: _ScalarResult(None))

        with self.assertRaises(HTTPException) as ctx:
            require_user_asset(db, "asset-1", "user-a")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_seed_dev_user_and_assets_is_noop_when_disabled(self) -> None:
        db = SimpleNamespace()

        result = seed_dev_user_and_assets(db, enabled=False)

        self.assertFalse(result)
