import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.asset_service import (  # noqa: E402
    collect_asset_storage_keys,
    extract_storage_key_from_public_url,
)


class AssetDeleteServiceHelpersTests(unittest.TestCase):
    def test_extract_storage_key_from_public_url(self) -> None:
        key = extract_storage_key_from_public_url(
            "https://bucket.oss-cn-hangzhou.aliyuncs.com/papers/users/u1/assets/a1/slides/v1/tts/slide-1.mp3"
        )
        self.assertEqual(key, "papers/users/u1/assets/a1/slides/v1/tts/slide-1.mp3")

    def test_collect_asset_storage_keys_merges_related_records(self) -> None:
        asset = SimpleNamespace(
            files=[
                SimpleNamespace(storage_key="papers/users/u1/assets/a1/original/paper.pdf"),
            ],
            document_parses=[
                SimpleNamespace(
                    markdown_storage_key="papers/users/u1/assets/a1/parses/p1/content.md",
                    json_storage_key="papers/users/u1/assets/a1/parses/p1/content.json",
                    raw_response_storage_key="papers/users/u1/assets/a1/parses/p1/raw.zip",
                )
            ],
            mindmaps=[SimpleNamespace(storage_key="papers/users/u1/assets/a1/mindmap/v1.json")],
            presentation=SimpleNamespace(
                tts_manifest={
                    "pages": [
                        {
                            "audio_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/papers/users/u1/assets/a1/slides/v2/tts/s1.mp3"
                        }
                    ]
                }
            ),
        )

        keys = collect_asset_storage_keys(asset)

        self.assertIn("papers/users/u1/assets/a1/original/paper.pdf", keys)
        self.assertIn("papers/users/u1/assets/a1/parses/p1/content.md", keys)
        self.assertIn("papers/users/u1/assets/a1/parses/p1/content.json", keys)
        self.assertIn("papers/users/u1/assets/a1/parses/p1/raw.zip", keys)
        self.assertIn("papers/users/u1/assets/a1/mindmap/v1.json", keys)
        self.assertIn("papers/users/u1/assets/a1/slides/v2/tts/s1.mp3", keys)


if __name__ == "__main__":
    unittest.main()
