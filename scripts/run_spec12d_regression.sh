#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_DIR="$ROOT_DIR/backend"

MODE="${1:-quick}"

PYTHON_BIN="python3"
if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
fi

SUMMARY_PATH="backend/tests/fixtures/spec12d_summary_pass.csv"

echo "[spec12d] mode=$MODE"
echo "[spec12d] python=$PYTHON_BIN"

echo "[spec12d] backend tests"
(cd "$BACKEND_DIR" && "$PYTHON_BIN" -m unittest \
  tests/test_spec12d_benchmark_service.py \
  tests/test_llm_prompt_compaction.py \
  tests/test_retrieval_hybrid_rrf.py \
  tests/test_query_rewrite_service.py \
  tests/test_rag_eval_s0_runner.py -v)

echo "[spec12d] backend compile check"
(cd "$BACKEND_DIR" && "$PYTHON_BIN" -m compileall app main.py)

echo "[spec12d] frontend build"
(cd frontend && npm run build)

if [ "$MODE" = "full" ]; then
  SUMMARY_PATH="docs/specs/spec-12d-results-final-v2/s0_summary.csv"
  echo "[spec12d] running full benchmark (80q * 3 runs, single-turn)"
  (cd "$ROOT_DIR" && "$PYTHON_BIN" backend/tests/rag_eval_s0_runner.py \
    --dataset docs/specs/spec-12d-question-dataset.jsonl \
    --output-dir docs/specs/spec-12d-results-final-v2 \
    --base-url http://localhost:8000 \
    --runs 3 \
    --top-k 5 \
    --strategy S0 \
    --expected-total 80 \
    --expected-asset-count 4 \
    --expected-per-asset 20 \
    --expected-per-language-per-asset 10 \
    --single-turn \
    --checkpoint-every 20)
fi

echo "[spec12d] gate check: $SUMMARY_PATH"
"$PYTHON_BIN" backend/scripts/spec12d_gate.py \
  --summary "$SUMMARY_PATH" \
  --min-hit-rate 0.92 \
  --min-citation-rate 0.92 \
  --max-e2e-p95-ms 8000

echo "[spec12d] done"
