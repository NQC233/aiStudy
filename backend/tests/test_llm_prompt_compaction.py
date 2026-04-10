import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.schemas.document_chunk import RetrievalSearchHit
from app.services.llm_service import _build_context_lines


class LlmPromptCompactionTests(unittest.TestCase):
    def test_build_context_lines_limits_hit_count(self) -> None:
        hits = [
            RetrievalSearchHit(
                chunk_id=f"c{i}",
                score=0.9,
                text="hello",
                page_start=1,
                page_end=1,
                paragraph_start=1,
                paragraph_end=1,
                block_ids=[f"b{i}"],
                section_path=["sec"],
                quote_text="q",
            )
            for i in range(1, 6)
        ]
        context = _build_context_lines(hits)
        self.assertIn("[1]", context)
        self.assertIn(f"[{settings.qa_context_max_hits}]", context)
        self.assertNotIn(f"[{settings.qa_context_max_hits + 1}]", context)

    def test_build_context_lines_clips_long_text(self) -> None:
        long_text = "a" * 1200
        hits = [
            RetrievalSearchHit(
                chunk_id="c1",
                score=0.9,
                text=long_text,
                page_start=1,
                page_end=1,
                paragraph_start=1,
                paragraph_end=1,
                block_ids=["b1"],
                section_path=["sec"],
                quote_text="q",
            )
        ]
        context = _build_context_lines(hits)
        self.assertIn("...", context)


if __name__ == "__main__":
    unittest.main()
