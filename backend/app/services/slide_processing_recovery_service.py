from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


_ACTIVE_TASK_STATES = {"PENDING", "RECEIVED", "STARTED", "RETRY", "SUCCESS"}


def _coerce_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _latest_processing_timestamp(asset: object, presentation: object | None) -> datetime | None:
    candidates = [
        _coerce_datetime(getattr(asset, "updated_at", None)),
        _coerce_datetime(getattr(presentation, "updated_at", None)),
    ]
    available = [item for item in candidates if item is not None]
    if not available:
        return None
    return max(available)


def _get_task_runtime_state(task_id: str) -> str | None:
    task_id = task_id.strip()
    if not task_id:
        return None
    try:
        state = AsyncResult(task_id, app=celery_app).state
    except Exception:
        logger.exception("Failed to inspect slides task state: task_id=%s", task_id)
        return None
    if not isinstance(state, str):
        return None
    normalized_state = state.strip().upper()
    return normalized_state or None


def recover_stale_slides_processing(
    db: Session,
    *,
    asset: object,
    presentation: object | None,
) -> str | None:
    if getattr(asset, "slides_status", None) != "processing":
        return None
    if presentation is None or getattr(presentation, "status", None) != "processing":
        return None

    last_updated_at = _latest_processing_timestamp(asset, presentation)
    if last_updated_at is None:
        return None

    timeout_sec = max(int(settings.slides_processing_stale_timeout_sec or 0), 0)
    stale_deadline = last_updated_at.timestamp() + timeout_sec
    now = datetime.now(UTC).timestamp()
    if now < stale_deadline:
        return None

    active_run_token = getattr(presentation, "active_run_token", None)
    if isinstance(active_run_token, str) and active_run_token.strip():
        task_state = _get_task_runtime_state(active_run_token)
        if task_state in _ACTIVE_TASK_STATES:
            logger.info(
                "Skip stale slides recovery because task is still recoverable: asset_id=%s task_id=%s task_state=%s",
                getattr(asset, "id", "unknown"),
                active_run_token,
                task_state,
            )
            return None

    recovered_at = datetime.now(UTC).isoformat()
    stale_meta: dict[str, Any] = {
        "reason": "slides_processing_timeout",
        "timeout_sec": timeout_sec,
        "stale_since": last_updated_at.isoformat(),
        "recovered_at": recovered_at,
    }
    error_meta = getattr(presentation, "error_meta", None)
    if not isinstance(error_meta, dict):
        error_meta = {}

    setattr(asset, "slides_status", "failed")
    setattr(presentation, "status", "failed")
    setattr(presentation, "active_run_token", None)
    setattr(
        presentation,
        "error_meta",
        {
            **error_meta,
            "stale_processing_recovery": stale_meta,
        },
    )
    db.commit()
    try:
        db.refresh(asset)
    except Exception:  # pragma: no cover - fake dbs may no-op or omit refresh support
        pass
    try:
        db.refresh(presentation)
    except Exception:  # pragma: no cover - fake dbs may no-op or omit refresh support
        pass

    logger.warning(
        "Recovered stale slides processing state: asset_id=%s stale_since=%s timeout_sec=%s",
        getattr(asset, "id", "unknown"),
        stale_meta["stale_since"],
        timeout_sec,
    )
    return "stale_processing_recovered"
