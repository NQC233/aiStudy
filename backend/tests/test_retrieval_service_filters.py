import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.document_chunk import RetrievalSearchHit
from app.services.retrieval_service import _section_bias
from app.services.retrieval_service import _build_retrieval_hits
from app.services.retrieval_service import _rerank_retrieval_hits


class RetrievalServiceFilterTests(unittest.TestCase):
    def test_build_retrieval_hits_filters_low_signal_results(self) -> None:
        rows = [
            (
                type(
                    "Chunk",
                    (),
                    {
                        "id": "c-author",
                        "text_content": "Ashish Vaswani Google Brain avaswani@google.com",
                        "page_start": 1,
                        "page_end": 1,
                        "paragraph_start": 3,
                        "paragraph_end": 3,
                        "block_ids": ["blk-author-1"],
                        "section_path": ["Attention Is All You Need", "Attention Is All You Need"],
                    },
                )(),
                0.1,
            ),
            (
                type(
                    "Chunk",
                    (),
                    {
                        "id": "c-good",
                        "text_content": "Table 2 summarizes our results and compares translation quality and training costs.",
                        "page_start": 8,
                        "page_end": 8,
                        "paragraph_start": 101,
                        "paragraph_end": 101,
                        "block_ids": ["blk-0101"],
                        "section_path": ["Attention Is All You Need", "6.1 Machine Translation"],
                    },
                )(),
                0.2,
            ),
        ]

        results = _build_retrieval_hits(rows)

        self.assertEqual([item.chunk_id for item in results], ["c-good"])

    def test_rerank_retrieval_hits_prefers_intro_for_motivation_queries(self) -> None:
        hits = [
            RetrievalSearchHit(
                chunk_id="c-training",
                score=0.9,
                text="This section describes the training regime for our models.",
                page_start=7,
                page_end=7,
                paragraph_start=81,
                paragraph_end=81,
                block_ids=["blk-0081"],
                section_path=["Attention Is All You Need", "5 Training"],
                quote_text="This section describes the training regime for our models.",
            ),
            RetrievalSearchHit(
                chunk_id="c-intro",
                score=0.82,
                text="Recurrent models preclude parallelization and limit learning on long sequences.",
                page_start=2,
                page_end=2,
                paragraph_start=18,
                paragraph_end=18,
                block_ids=["blk-0018"],
                section_path=["Attention Is All You Need", "1 Introduction"],
                quote_text="Recurrent models preclude parallelization and limit learning on long sequences.",
            ),
        ]

        reranked = _rerank_retrieval_hits("research problem and motivation", hits)

        self.assertEqual([item.chunk_id for item in reranked], ["c-intro", "c-training"])

    def test_section_bias_penalizes_training_and_optimizer_for_motivation_queries(self) -> None:
        self.assertGreater(
            _section_bias("research problem and motivation", ["Attention Is All You Need", "1 Introduction"]),
            0,
        )
        self.assertGreater(
            _section_bias("research problem and motivation", ["Attention Is All You Need", "Abstract"]),
            0,
        )
        self.assertGreater(
            _section_bias("research problem and motivation", ["Attention Is All You Need", "4 Why Self-Attention"]),
            0,
        )
        self.assertLess(
            _section_bias("research problem and motivation", ["Attention Is All You Need", "5 Training"]),
            0,
        )
        self.assertLess(
            _section_bias("research problem and motivation", ["Attention Is All You Need", "5.3 Optimizer"]),
            0,
        )

    def test_section_bias_prefers_architecture_over_training_for_method_queries(self) -> None:
        self.assertGreater(
            _section_bias("method overview and framework", ["Attention Is All You Need", "3 Model Architecture"]),
            0,
        )
        self.assertLess(
            _section_bias("method overview and framework", ["Attention Is All You Need", "5 Training"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
