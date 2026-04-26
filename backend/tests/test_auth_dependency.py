import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from app.api.deps.auth import get_current_user


class AuthDependencyShapeTests(unittest.TestCase):
    def test_get_current_user_rejects_unknown_subject(self) -> None:
        db = SimpleNamespace(get=lambda _model, _id: None)

        with patch("app.api.deps.auth.decode_access_token", return_value={"sub": "user-missing"}):
            with self.assertRaises(HTTPException) as ctx:
                get_current_user(db=db, authorization="Bearer token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_get_current_user_returns_db_user(self) -> None:
        user = SimpleNamespace(id="user-1")
        db = SimpleNamespace(get=lambda _model, _id: user)

        with patch("app.api.deps.auth.decode_access_token", return_value={"sub": "user-1"}):
            current_user = get_current_user(db=db, authorization="Bearer token")

        self.assertEqual(current_user.id, "user-1")
