import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.query_rewrite_service import prepare_retrieval_query


class QueryRewriteServiceTests(unittest.TestCase):
    def test_returns_original_when_rewrite_disabled(self) -> None:
        query = "What is residual learning?"
        self.assertEqual(
            prepare_retrieval_query(query=query, rewrite_query=False),
            query,
        )

    def test_returns_original_for_non_cjk_query_when_enabled(self) -> None:
        query = "What does RAG-Sequence mean?"
        self.assertEqual(
            prepare_retrieval_query(query=query, rewrite_query=True),
            query,
        )

    def test_rewrites_cjk_query_when_rewriter_returns_text(self) -> None:
        rewritten = prepare_retrieval_query(
            query="这篇论文的核心贡献是什么？",
            rewrite_query=True,
            rewrite_func=lambda _: "core contributions of this paper",
        )
        self.assertEqual(rewritten, "core contributions of this paper")

    def test_falls_back_to_original_when_rewriter_fails(self) -> None:
        def _boom(_: str) -> str:
            raise RuntimeError("upstream down")

        query = "请总结主要方法"
        rewritten = prepare_retrieval_query(
            query=query,
            rewrite_query=True,
            rewrite_func=_boom,
        )
        self.assertEqual(rewritten, query)


if __name__ == "__main__":
    unittest.main()
