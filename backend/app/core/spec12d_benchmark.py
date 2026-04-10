from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Spec12dGateResult:
    passed: bool
    reason: str
    hit_rate: float
    citation_rate: float
    e2e_p95_ms: float


def evaluate_spec12d_gate(
    rows: list[dict[str, str]],
    *,
    min_hit_rate: float,
    min_citation_rate: float,
    max_e2e_p95_ms: float,
) -> Spec12dGateResult:
    if not rows:
        return Spec12dGateResult(
            passed=False,
            reason="empty summary rows",
            hit_rate=0.0,
            citation_rate=0.0,
            e2e_p95_ms=0.0,
        )

    hit_rate = sum(float(row["retrieval_hit_rate"]) for row in rows) / len(rows)
    citation_rate = sum(float(row["citation_correct_rate"]) for row in rows) / len(rows)
    e2e_p95_ms = max(float(row["e2e_p95_ms"]) for row in rows)

    if hit_rate < min_hit_rate:
        return Spec12dGateResult(
            passed=False,
            reason=f"hit_rate below threshold: {hit_rate:.4f} < {min_hit_rate:.4f}",
            hit_rate=hit_rate,
            citation_rate=citation_rate,
            e2e_p95_ms=e2e_p95_ms,
        )

    if citation_rate < min_citation_rate:
        return Spec12dGateResult(
            passed=False,
            reason=(
                f"citation_rate below threshold: {citation_rate:.4f} < {min_citation_rate:.4f}"
            ),
            hit_rate=hit_rate,
            citation_rate=citation_rate,
            e2e_p95_ms=e2e_p95_ms,
        )

    if e2e_p95_ms > max_e2e_p95_ms:
        return Spec12dGateResult(
            passed=False,
            reason=(
                f"e2e_p95_ms above threshold: {e2e_p95_ms:.2f} > {max_e2e_p95_ms:.2f}"
            ),
            hit_rate=hit_rate,
            citation_rate=citation_rate,
            e2e_p95_ms=e2e_p95_ms,
        )

    return Spec12dGateResult(
        passed=True,
        reason="gate passed",
        hit_rate=hit_rate,
        citation_rate=citation_rate,
        e2e_p95_ms=e2e_p95_ms,
    )
