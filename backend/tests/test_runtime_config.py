import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings


class RuntimeConfigTests(unittest.TestCase):
    def test_default_cors_origin_list_allows_localhost_and_loopback_frontend(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual(
            settings.cors_origin_list,
            [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ],
        )

    def test_default_slides_batch_html_settings_are_present(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual(settings.slides_html_batch_timeout_sec, 600)
        self.assertEqual(settings.slides_html_batch_max_pages, 12)
        self.assertEqual(settings.slides_html_batch_chunk_size, 4)
        self.assertEqual(settings.slides_html_rebuild_timeout_sec, 180)
        self.assertEqual(settings.slides_html_failed_only_max_ratio, 0.3)

    def test_default_slides_processing_stale_timeout_is_extended(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual(settings.slides_processing_stale_timeout_sec, 1800)

    def test_default_auth_settings_are_present(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual(settings.auth_jwt_secret, "change-me-in-env")
        self.assertEqual(settings.auth_access_token_expire_minutes, 60 * 24 * 7)
        self.assertFalse(settings.auth_dev_bypass_enabled)
        self.assertTrue(settings.auth_default_account_enabled)
        self.assertEqual(settings.auth_default_account_id, "default-demo-user")
        self.assertEqual(settings.auth_default_account_email, "demo@paper-learning.local")
        self.assertEqual(settings.auth_default_account_name, "默认演示账户")
        self.assertEqual(settings.auth_default_account_password, "paper123456")
