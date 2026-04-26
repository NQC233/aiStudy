import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException

from app.api.deps.auth import resolve_bearer_token
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import login_user, register_user


class AuthRouteShapeTests(unittest.TestCase):
    def test_resolve_bearer_token_accepts_standard_header(self) -> None:
        token = resolve_bearer_token("Bearer abc.def.ghi")
        self.assertEqual(token, "abc.def.ghi")

    def test_resolve_bearer_token_rejects_missing_header(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            resolve_bearer_token(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_register_and_login_functions_exist(self) -> None:
        self.assertTrue(callable(register_user))
        self.assertTrue(callable(login_user))
        self.assertEqual(
            RegisterRequest(email="a@example.com", password="paper-pass-123", display_name="A").email,
            "a@example.com",
        )
        self.assertEqual(LoginRequest(email="a@example.com", password="paper-pass-123").email, "a@example.com")
