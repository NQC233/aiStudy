import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.retrieval_service import merge_rrf_scores, rerank_candidates


class RetrievalHybridRrfTests(unittest.TestCase):
    def test_merge_rrf_scores_combines_vector_and_keyword_ranks(self) -> None:
        vector_ids = ["c1", "c2", "c3"]
        keyword_ids = ["c3", "c4", "c2"]

        merged = merge_rrf_scores(vector_ids=vector_ids, keyword_ids=keyword_ids, rrf_k=60)

        self.assertEqual(merged[0], "c3")
        self.assertIn("c2", merged)
        self.assertIn("c4", merged)

    def test_merge_rrf_scores_preserves_unique_candidates(self) -> None:
        vector_ids = ["v1", "v2"]
        keyword_ids = []

        merged = merge_rrf_scores(vector_ids=vector_ids, keyword_ids=keyword_ids, rrf_k=60)

        self.assertEqual(merged, ["v1", "v2"])

    def test_rerank_candidates_prioritizes_query_overlap(self) -> None:
        query = "residual learning framework"
        candidates = [
            {
                "chunk_id": "c1",
                "text": "This section introduces optimization details.",
                "base_score": 0.9,
            },
            {
                "chunk_id": "c2",
                "text": "We propose a residual learning framework for deep nets.",
                "base_score": 0.7,
            },
        ]

        ranked = rerank_candidates(query=query, candidates=candidates, top_n=2)

        self.assertEqual(ranked[0]["chunk_id"], "c2")

    def test_rerank_candidates_respects_top_n(self) -> None:
        ranked = rerank_candidates(
            query="transformer attention",
            candidates=[
                {"chunk_id": "c1", "text": "transformer attention", "base_score": 0.5},
                {"chunk_id": "c2", "text": "transformer", "base_score": 0.4},
                {"chunk_id": "c3", "text": "other", "base_score": 0.9},
            ],
            top_n=2,
        )
        self.assertEqual(len(ranked), 2)


if __name__ == "__main__":
    unittest.main()
