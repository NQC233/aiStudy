import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.routes.chat import (
    create_chat_session_message_endpoint,
    list_chat_session_messages_endpoint,
)
from app.schemas.chat import ChatMessageCreateRequest
from app.services.chat_service import require_user_session


class _ScalarResult:
    def __init__(self, obj):
        self.obj = obj

    def first(self):
        return self.obj


class ChatRouteUserPropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SimpleNamespace()
        self.current_user = SimpleNamespace(id="user-123")

    def test_list_chat_session_messages_passes_current_user_id(self) -> None:
        response = {"session_id": "session-1", "asset_id": "asset-1", "messages": []}

        with patch("app.api.routes.chat.list_chat_session_messages", return_value=response) as list_mock:
            result = list_chat_session_messages_endpoint(
                session_id="session-1",
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        list_mock.assert_called_once_with(self.db, "session-1", "user-123")

    def test_create_chat_session_message_passes_current_user_id(self) -> None:
        payload = ChatMessageCreateRequest(question="What is this paper about?")
        response = {"session_id": "session-1", "question_message_id": "m1", "answer_message_id": "m2", "answer": "summary", "citations": []}

        with patch("app.api.routes.chat.create_chat_session_message", return_value=response) as create_mock:
            result = create_chat_session_message_endpoint(
                session_id="session-1",
                payload=payload,
                db=self.db,
                current_user=self.current_user,
            )

        self.assertEqual(result, response)
        create_mock.assert_called_once_with(self.db, "session-1", "user-123", payload)


class ChatOwnerCheckTests(unittest.TestCase):
    def test_require_user_session_rejects_other_users_session(self) -> None:
        db = SimpleNamespace(scalars=lambda _statement: _ScalarResult(None))

        with self.assertRaises(HTTPException) as ctx:
            require_user_session(db, "session-1", "user-a")

        self.assertEqual(ctx.exception.status_code, 404)
