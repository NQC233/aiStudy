import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.slide_dsl import SlideTtsManifest, SlideTtsManifestItem
from app.services.slide_tts_service import (
    choose_tts_target_slide_keys,
    enqueue_manifest_targets,
    resolve_tts_voice_for_model,
)


class SlideTtsServiceTests(unittest.TestCase):
    def test_choose_tts_target_slide_keys_includes_next_when_enabled(self) -> None:
        slide_keys = ["s1", "s2", "s3"]
        targets = choose_tts_target_slide_keys(
            slide_keys, page_index=1, prefetch_next=True
        )
        self.assertEqual(targets, ["s2", "s3"])

    def test_choose_tts_target_slide_keys_bounds_check(self) -> None:
        slide_keys = ["s1"]
        with self.assertRaises(ValueError):
            choose_tts_target_slide_keys(slide_keys, page_index=2, prefetch_next=True)

    def test_enqueue_manifest_targets_only_marks_pending_or_failed(self) -> None:
        manifest = SlideTtsManifest(
            pages=[
                SlideTtsManifestItem(slide_key="s1", status="ready"),
                SlideTtsManifestItem(
                    slide_key="s2",
                    status="failed",
                    retry_meta={"attempt": 2, "auto_retry_pending": True},
                ),
                SlideTtsManifestItem(slide_key="s3", status="pending"),
            ]
        )

        enqueued = enqueue_manifest_targets(manifest, ["s1", "s2", "s3"])

        self.assertEqual(enqueued, ["s2", "s3"])
        statuses = {item.slide_key: item.status for item in manifest.pages}
        self.assertEqual(statuses["s1"], "ready")
        self.assertEqual(statuses["s2"], "processing")
        self.assertEqual(statuses["s3"], "processing")
        self.assertIsNone(manifest.pages[1].retry_meta)

    def test_resolve_tts_voice_for_cosyvoice_v3_alias(self) -> None:
        self.assertEqual(
            resolve_tts_voice_for_model("cosyvoice-v3-flash", "longxiaochun"),
            "longxiaochun_v3",
        )

    def test_resolve_tts_voice_keeps_other_values(self) -> None:
        self.assertEqual(
            resolve_tts_voice_for_model("cosyvoice-v3-flash", "longanyang"),
            "longanyang",
        )
        self.assertEqual(
            resolve_tts_voice_for_model("qwen-tts-latest", "longxiaochun"),
            "longxiaochun",
        )


if __name__ == "__main__":
    unittest.main()
