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
