import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.routes.notes import delete_note_endpoint, update_note_endpoint
from app.schemas.note import UpdateNoteRequest
from app.services.note_service import _require_user_note


class _ScalarResult:
    def __init__(self, obj):
        self.obj = obj

    def first(self):
        return self.obj


class NoteRouteUserPropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SimpleNamespace()
        self.current_user = SimpleNamespace(id="user-123")

    def test_update_note_passes_current_user_id(self) -> None:
        payload = UpdateNoteRequest(content="updated")
        response = {"id": "note-1"}

        with patch("app.api.routes.notes.update_note", return_value=response) as update_mock:
            result = update_note_endpoint(
                note_id="note-1",
                payload=payload,
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        update_mock.assert_called_once_with(
            db=self.db,
            note_id="note-1",
            user_id="user-123",
            payload=payload,
        )

    def test_delete_note_passes_current_user_id(self) -> None:
        response = {"note_id": "note-1", "deleted": True}

        with patch("app.api.routes.notes.delete_note", return_value=response) as delete_mock:
            result = delete_note_endpoint(
                note_id="note-1",
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        delete_mock.assert_called_once_with(
            db=self.db,
            note_id="note-1",
            user_id="user-123",
        )


class NoteOwnerCheckTests(unittest.TestCase):
    def test_require_user_note_keeps_returning_404_for_other_user(self) -> None:
        db = SimpleNamespace(scalars=lambda _statement: _ScalarResult(None))

        with self.assertRaises(HTTPException) as ctx:
            _require_user_note(db, "note-1", "user-a")

        self.assertEqual(ctx.exception.status_code, 404)
