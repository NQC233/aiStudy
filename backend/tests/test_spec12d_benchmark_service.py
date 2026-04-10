import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.spec12d_benchmark import evaluate_spec12d_gate


class Spec12dBenchmarkServiceTests(unittest.TestCase):
    def test_evaluate_gate_passes_when_quality_and_latency_meet_threshold(self) -> None:
        rows = [
            {
                "strategy": "S0",
                "run_index": "1",
                "question_lang": "en",
                "sample_count": "40",
                "retrieval_hit_rate": "0.925",
                "citation_correct_rate": "0.925",
                "e2e_p95_ms": "7800",
            },
            {
                "strategy": "S0",
                "run_index": "1",
                "question_lang": "zh",
                "sample_count": "40",
                "retrieval_hit_rate": "0.925",
                "citation_correct_rate": "0.925",
                "e2e_p95_ms": "7600",
            },
        ]

        result = evaluate_spec12d_gate(
            rows,
            min_hit_rate=0.92,
            min_citation_rate=0.92,
            max_e2e_p95_ms=8000,
        )

        self.assertTrue(result.passed)

    def test_evaluate_gate_fails_when_latency_exceeds_threshold(self) -> None:
        rows = [
            {
                "strategy": "S0",
                "run_index": "1",
                "question_lang": "en",
                "sample_count": "40",
                "retrieval_hit_rate": "0.925",
                "citation_correct_rate": "0.925",
                "e2e_p95_ms": "9200",
            }
        ]

        result = evaluate_spec12d_gate(
            rows,
            min_hit_rate=0.92,
            min_citation_rate=0.92,
            max_e2e_p95_ms=8000,
        )

        self.assertFalse(result.passed)
        self.assertIn("e2e_p95_ms", result.reason)


if __name__ == "__main__":
    unittest.main()
