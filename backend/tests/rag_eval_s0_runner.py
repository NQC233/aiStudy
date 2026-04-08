from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class QuestionItem:
    question_id: str
    asset_id: str
    question_lang: str
    question: str
    expected_block_id: str
    expected_page: int | None
    expected_paragraph: int | None
    answer_keypoints: list[str]


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data: bytes | None = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url=url, method=method, data=data, headers=headers)
    try:
        with urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _load_questions(dataset_path: Path) -> list[QuestionItem]:
    questions: list[QuestionItem] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            questions.append(
                QuestionItem(
                    question_id=str(payload["question_id"]),
                    asset_id=str(payload["asset_id"]),
                    question_lang=str(payload["question_lang"]),
                    question=str(payload["question"]),
                    expected_block_id=str(payload["expected_block_id"]),
                    expected_page=payload.get("expected_page"),
                    expected_paragraph=payload.get("expected_paragraph"),
                    answer_keypoints=[str(item) for item in payload.get("answer_keypoints", [])],
                )
            )
            if questions[-1].question_lang not in {"zh", "en"}:
                raise ValueError(f"Line {line_number}: question_lang must be 'zh' or 'en'")
    if not questions:
        raise ValueError("Dataset is empty")
    return questions


def _create_chat_session(base_url: str, asset_id: str, run_index: int, strategy: str) -> str:
    payload = {"title": f"spec12d-{strategy}-run{run_index}"}
    response = _request_json(
        "POST",
        f"{base_url}/api/assets/{asset_id}/chat/sessions",
        payload=payload,
    )
    return str(response["id"])


def _contains_expected_block(items: list[dict[str, Any]], expected_block_id: str) -> bool:
    for item in items:
        block_ids = item.get("block_ids") or []
        if expected_block_id in block_ids:
            return True
    return False


def _write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "strategy",
        "run_index",
        "question_id",
        "asset_id",
        "question_lang",
        "question",
        "expected_block_id",
        "retrieval_ms",
        "e2e_ms",
        "retrieval_hit",
        "citation_correct",
        "retrieval_result_count",
        "citation_count",
        "answer",
        "answer_score",
        "error_type",
        "error_message",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["strategy"]), int(row["run_index"]), str(row["question_lang"]))
        grouped.setdefault(key, []).append(row)

    summary_fieldnames = [
        "strategy",
        "run_index",
        "question_lang",
        "sample_count",
        "retrieval_hit_rate",
        "citation_correct_rate",
        "e2e_p50_ms",
        "e2e_p95_ms",
        "retrieval_p50_ms",
        "retrieval_p95_ms",
        "error_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fieldnames)
        writer.writeheader()
        for (strategy, run_index, question_lang), items in sorted(grouped.items()):
            retrieval_costs = [float(item["retrieval_ms"]) for item in items if item["retrieval_ms"] != ""]
            e2e_costs = [float(item["e2e_ms"]) for item in items if item["e2e_ms"] != ""]
            retrieval_hits = [item["retrieval_hit"] == "1" for item in items]
            citation_hits = [item["citation_correct"] == "1" for item in items]
            errors = [item for item in items if item["error_type"]]
            writer.writerow(
                {
                    "strategy": strategy,
                    "run_index": run_index,
                    "question_lang": question_lang,
                    "sample_count": len(items),
                    "retrieval_hit_rate": round(sum(retrieval_hits) / len(items), 4),
                    "citation_correct_rate": round(sum(citation_hits) / len(items), 4),
                    "e2e_p50_ms": round(statistics.median(e2e_costs), 2) if e2e_costs else "",
                    "e2e_p95_ms": round(_percentile(e2e_costs, 95), 2) if e2e_costs else "",
                    "retrieval_p50_ms": round(statistics.median(retrieval_costs), 2)
                    if retrieval_costs
                    else "",
                    "retrieval_p95_ms": round(_percentile(retrieval_costs, 95), 2)
                    if retrieval_costs
                    else "",
                    "error_count": len(errors),
                }
            )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def run_s0_baseline(
    *,
    base_url: str,
    dataset_path: Path,
    output_dir: Path,
    runs: int,
    top_k: int,
    strategy: str,
) -> tuple[Path, Path]:
    questions = _load_questions(dataset_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    session_by_run_and_asset: dict[tuple[int, str], str] = {}

    for run_index in range(1, runs + 1):
        for question in questions:
            session_key = (run_index, question.asset_id)
            if session_key not in session_by_run_and_asset:
                session_by_run_and_asset[session_key] = _create_chat_session(
                    base_url=base_url,
                    asset_id=question.asset_id,
                    run_index=run_index,
                    strategy=strategy,
                )
            session_id = session_by_run_and_asset[session_key]

            row: dict[str, Any] = {
                "strategy": strategy,
                "run_index": run_index,
                "question_id": question.question_id,
                "asset_id": question.asset_id,
                "question_lang": question.question_lang,
                "question": question.question,
                "expected_block_id": question.expected_block_id,
                "retrieval_ms": "",
                "e2e_ms": "",
                "retrieval_hit": "0",
                "citation_correct": "0",
                "retrieval_result_count": "",
                "citation_count": "",
                "answer": "",
                "answer_score": "",
                "error_type": "",
                "error_message": "",
            }

            try:
                retrieval_start = time.perf_counter()
                retrieval = _request_json(
                    "POST",
                    f"{base_url}/api/assets/{question.asset_id}/retrieval/search",
                    payload={"query": question.question, "top_k": top_k},
                )
                row["retrieval_ms"] = round((time.perf_counter() - retrieval_start) * 1000, 2)
                retrieval_results = retrieval.get("results") or []
                row["retrieval_result_count"] = len(retrieval_results)
                row["retrieval_hit"] = (
                    "1" if _contains_expected_block(retrieval_results, question.expected_block_id) else "0"
                )

                e2e_start = time.perf_counter()
                chat = _request_json(
                    "POST",
                    f"{base_url}/api/chat/sessions/{session_id}/messages",
                    payload={"question": question.question, "top_k": top_k},
                )
                row["e2e_ms"] = round((time.perf_counter() - e2e_start) * 1000, 2)
                row["answer"] = chat.get("answer", "")
                citations = chat.get("citations") or []
                row["citation_count"] = len(citations)
                row["citation_correct"] = "1" if _contains_expected_block(citations, question.expected_block_id) else "0"
            except Exception as exc:
                row["error_type"] = type(exc).__name__
                row["error_message"] = str(exc)

            rows.append(row)

    rows_csv = output_dir / f"{strategy.lower()}_rows.csv"
    summary_csv = output_dir / f"{strategy.lower()}_summary.csv"
    _write_rows_csv(rows_csv, rows)
    _write_summary_csv(summary_csv, rows)
    return rows_csv, summary_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spec12D S0 baseline runner")
    parser.add_argument(
        "--dataset",
        required=True,
        help="JSONL dataset file path",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/specs/spec-12d-results",
        help="Output directory for CSV files",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="How many repeated runs",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Retrieval top-k",
    )
    parser.add_argument(
        "--strategy",
        default="S0",
        choices=["S0"],
        help="Strategy tag",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows_csv, summary_csv = run_s0_baseline(
        base_url=args.base_url.rstrip("/"),
        dataset_path=Path(args.dataset),
        output_dir=Path(args.output_dir),
        runs=args.runs,
        top_k=args.top_k,
        strategy=args.strategy,
    )
    print(f"Rows saved to: {rows_csv}")
    print(f"Summary saved to: {summary_csv}")


if __name__ == "__main__":
    main()
