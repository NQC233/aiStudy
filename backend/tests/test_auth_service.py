import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


class AuthSecurityTests(unittest.TestCase):
    def test_settings_expose_auth_defaults(self) -> None:
        settings = Settings(
            _env_file=None,
            auth_jwt_secret="test-secret",
            auth_access_token_expire_minutes=120,
        )

        self.assertEqual(settings.auth_jwt_secret, "test-secret")
        self.assertEqual(settings.auth_access_token_expire_minutes, 120)
        self.assertFalse(settings.auth_dev_bypass_enabled)

    def test_password_hash_round_trip(self) -> None:
        hashed = get_password_hash("paper-pass-123")

        self.assertNotEqual(hashed, "paper-pass-123")
        self.assertTrue(verify_password("paper-pass-123", hashed))
        self.assertFalse(verify_password("wrong-pass", hashed))

    def test_access_token_round_trip(self) -> None:
        with patch("app.core.security.settings.auth_jwt_secret", "0123456789abcdef0123456789abcdef"), patch(
            "app.core.security.settings.auth_access_token_expire_minutes",
            120,
        ):
            token = create_access_token(subject="user-1", email="user@example.com")
            payload = decode_access_token(token)

        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["email"], "user@example.com")
