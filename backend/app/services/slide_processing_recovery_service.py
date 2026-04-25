from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


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
