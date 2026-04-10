from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.spec12d_benchmark import evaluate_spec12d_gate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spec12D benchmark gate checker")
    parser.add_argument("--summary", required=True, help="Path to summary CSV")
    parser.add_argument("--min-hit-rate", type=float, default=0.92)
    parser.add_argument("--min-citation-rate", type=float, default=0.92)
    parser.add_argument("--max-e2e-p95-ms", type=float, default=8000.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"[gate] summary file not found: {summary_path}")
        return 2

    with summary_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    result = evaluate_spec12d_gate(
        rows,
        min_hit_rate=args.min_hit_rate,
        min_citation_rate=args.min_citation_rate,
        max_e2e_p95_ms=args.max_e2e_p95_ms,
    )

    print(
        "[gate] "
        f"passed={result.passed} "
        f"hit={result.hit_rate:.4f} "
        f"citation={result.citation_rate:.4f} "
        f"e2e_p95={result.e2e_p95_ms:.2f} "
        f"reason={result.reason}"
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
