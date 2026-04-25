from __future__ import annotations

from typing import Any

_RUNTIME_GATE_BLOCKED_STATUSES = {"failed", "blocked", "invalid"}


def _page_validation_status(page: dict[str, Any]) -> str:
    render_meta = page.get("render_meta")
    if not isinstance(render_meta, dict):
        return "passed"

    validation = render_meta.get("validation")
    if isinstance(validation, dict):
        status = validation.get("status")
        if isinstance(status, str) and status.strip():
            return status.strip().lower()
        if bool(validation.get("blocking", False)):
            return "blocked"

    gate_status = render_meta.get("runtime_gate_status")
    if isinstance(gate_status, str) and gate_status.strip():
        return gate_status.strip().lower()

    return "passed"


def _failed_page_numbers(rendered_pages: list[dict[str, object]]) -> list[int]:
    failed: list[int] = []
    for index, page in enumerate(rendered_pages, start=1):
        if _page_validation_status(page) in _RUNTIME_GATE_BLOCKED_STATUSES:
            failed.append(index)
    return failed


def _runtime_bundle_status(
    *,
    page_count: int,
    pages: list[dict[str, Any]],
    failed_page_numbers: list[int],
) -> str:
    if page_count <= 0 or not pages:
        return "not_ready"
    if not failed_page_numbers:
        return "ready"
    playable_page_count = max(0, len(pages) - len(failed_page_numbers))
    if playable_page_count > 0:
        return "partial_ready"
    return "not_ready"


def summarize_runtime_bundle(bundle: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        return {
            "page_count": 0,
            "playable_page_count": 0,
            "failed_page_numbers": [],
            "validation_summary": {
                "status": "not_ready",
                "page_count": 0,
                "playable_page_count": 0,
                "failed_page_numbers": [],
            },
        }

    pages = bundle.get("pages") if isinstance(bundle.get("pages"), list) else []
    page_count = int(bundle.get("page_count", len(pages)) or 0)
    if pages:
        failed_page_numbers = _failed_page_numbers(pages)
    else:
        failed_page_numbers = [
            int(value) for value in bundle.get("failed_page_numbers", []) if isinstance(value, int)
        ]
    playable_page_count = max(0, len(pages) - len(failed_page_numbers))
    validation_summary = bundle.get("validation_summary") if isinstance(bundle.get("validation_summary"), dict) else {}

    summary = {
        "status": _runtime_bundle_status(
            page_count=page_count,
            pages=pages,
            failed_page_numbers=failed_page_numbers,
        ),
        "page_count": page_count,
        "playable_page_count": playable_page_count,
        "failed_page_numbers": failed_page_numbers,
        **validation_summary,
    }
    summary["status"] = _runtime_bundle_status(
        page_count=page_count,
        pages=pages,
        failed_page_numbers=failed_page_numbers,
    )
    summary["page_count"] = page_count
    summary["playable_page_count"] = playable_page_count
    summary["failed_page_numbers"] = failed_page_numbers

    return {
        "page_count": page_count,
        "playable_page_count": playable_page_count,
        "failed_page_numbers": failed_page_numbers,
        "validation_summary": summary,
    }


def is_runtime_bundle_playable(bundle: dict[str, Any] | None) -> bool:
    summary = summarize_runtime_bundle(bundle)
    return summary["validation_summary"]["status"] in {"ready", "partial_ready"}


def build_runtime_bundle(rendered_pages: list[dict[str, object]]) -> dict[str, object]:
    failed_page_numbers = _failed_page_numbers(rendered_pages)
    playable_page_count = max(0, len(rendered_pages) - len(failed_page_numbers))
    return {
        "page_count": len(rendered_pages),
        "pages": rendered_pages,
        "playable_page_count": playable_page_count,
        "failed_page_numbers": failed_page_numbers,
        "validation_summary": {
            "status": _runtime_bundle_status(
                page_count=len(rendered_pages),
                pages=rendered_pages,
                failed_page_numbers=failed_page_numbers,
            ),
            "page_count": len(rendered_pages),
            "playable_page_count": playable_page_count,
            "failed_page_numbers": failed_page_numbers,
        },
    }
