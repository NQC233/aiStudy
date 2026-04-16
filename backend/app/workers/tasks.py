from __future__ import annotations

import logging

from celery import Task
from celery.exceptions import Retry
from sqlalchemy import select

from app.core.config import settings
from app.core.task_reliability import (
    build_retry_snapshot,
    classify_task_exception,
    compute_retry_delay_seconds,
)
from app.db.session import SessionLocal
from app.models.asset import Asset
from app.models.document_parse import DocumentParse
from app.models.mindmap import Mindmap
from app.models.presentation import Presentation
from app.services import run_asset_mindmap_pipeline
from app.services.document_parse_service import run_parse_pipeline
from app.services.retrieval_service import (
    enqueue_asset_chunk_rebuild,
    run_asset_kb_pipeline,
)
from app.services.slide_tts_service import run_asset_slide_tts_pipeline
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _retry_limit() -> int:
    return max(0, settings.celery_task_max_retries)


def _should_retry(task: Task, retryable: bool) -> bool:
    return retryable and task.request.retries < _retry_limit()


def _build_task_retry_snapshot(task: Task) -> tuple[dict[str, str | int | bool], int]:
    attempt = task.request.retries + 1
    delay = compute_retry_delay_seconds(
        attempt=attempt,
        base_seconds=settings.celery_task_retry_backoff_sec,
        max_seconds=settings.celery_task_retry_backoff_max_sec,
        use_jitter=settings.celery_task_retry_jitter,
    )
    snapshot = build_retry_snapshot(
        attempt=attempt,
        max_retries=_retry_limit(),
        delay_seconds=delay,
    )
    return snapshot, delay


def _mark_parse_retry_pending(
    asset_id: str, retry_snapshot: dict[str, str | int | bool], error_message: str
) -> None:
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if asset is not None:
            asset.status = "processing"
            asset.parse_status = "processing"
            asset.parse_error_message = error_message

        latest_parse = db.scalars(
            select(DocumentParse)
            .where(DocumentParse.asset_id == asset_id)
            .order_by(DocumentParse.created_at.desc())
        ).first()
        if latest_parse is not None:
            latest_parse.parser_meta = {
                **latest_parse.parser_meta,
                "retry": retry_snapshot,
            }
        db.commit()
    finally:
        db.close()


def _mark_kb_retry_pending(asset_id: str) -> None:
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if asset is not None:
            asset.kb_status = "processing"
            db.commit()
    finally:
        db.close()


def _mark_mindmap_retry_pending(
    asset_id: str,
    retry_snapshot: dict[str, str | int | bool],
    error_message: str,
) -> None:
    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if asset is not None:
            asset.mindmap_status = "processing"

        latest_mindmap = db.scalars(
            select(Mindmap)
            .where(Mindmap.asset_id == asset_id)
            .order_by(Mindmap.version.desc(), Mindmap.created_at.desc())
        ).first()
        if latest_mindmap is not None:
            latest_mindmap.meta = {
                **(latest_mindmap.meta or {}),
                "failure_reason": error_message,
                "retry": retry_snapshot,
            }
        db.commit()
    finally:
        db.close()


def _retry_context(task: Task) -> dict[str, str | int | bool | None]:
    return {
        "attempt": task.request.retries + 1,
        "max_retries": _retry_limit(),
        "next_retry_eta": None,
        "auto_retry_pending": False,
    }


def _mark_tts_retry_pending(
    asset_id: str,
    slide_key: str,
    retry_snapshot: dict[str, str | int | bool],
    error_message: str,
    error_code: str,
) -> None:
    db = SessionLocal()
    try:
        presentation = db.scalars(
            select(Presentation)
            .where(Presentation.asset_id == asset_id)
            .with_for_update()
        ).first()
        if presentation is None or not isinstance(presentation.tts_manifest, dict):
            return

        manifest_payload = dict(presentation.tts_manifest)
        pages = manifest_payload.get("pages")
        if not isinstance(pages, list):
            return

        for page in pages:
            if not isinstance(page, dict) or page.get("slide_key") != slide_key:
                continue
            page["status"] = "processing"
            page["error_message"] = error_message
            page["retry_meta"] = {
                **retry_snapshot,
                "error_code": error_code,
            }
            presentation.tts_manifest = manifest_payload
            db.commit()
            return
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """最小演示任务，用于确认 Celery Worker 可以正常注册任务。"""
    return "pong"


@celery_app.task(bind=True, name="app.workers.tasks.enqueue_parse_asset")
def enqueue_parse_asset(self: Task, asset_id: str) -> dict[str, str]:
    """执行资产解析任务。"""
    db = SessionLocal()
    try:
        document_parse = run_parse_pipeline(
            db, asset_id, retry_meta=_retry_context(self)
        )
        if document_parse.status == "succeeded":
            enqueue_generate_asset_mindmap.delay(asset_id)
            _, should_enqueue = enqueue_asset_chunk_rebuild(db, asset_id)
            if should_enqueue:
                enqueue_build_asset_kb.delay(asset_id)
            return {
                "asset_id": asset_id,
                "parse_id": document_parse.id,
                "status": document_parse.status,
            }

        failure_meta = document_parse.parser_meta.get("failure")
        retryable = (
            isinstance(failure_meta, dict) and failure_meta.get("retryable") is True
        )
        error_message = (
            str(failure_meta.get("error_message"))
            if isinstance(failure_meta, dict)
            and isinstance(failure_meta.get("error_message"), str)
            else "解析失败。"
        )
        if _should_retry(self, retryable):
            retry_snapshot, delay = _build_task_retry_snapshot(self)
            _mark_parse_retry_pending(asset_id, retry_snapshot, error_message)
            logger.warning(
                "解析任务进入自动重试: asset_id=%s attempt=%s max_retries=%s error=%s",
                asset_id,
                retry_snapshot["attempt"],
                retry_snapshot["max_retries"],
                error_message,
            )
            raise self.retry(
                exc=RuntimeError(error_message),
                countdown=delay,
                max_retries=_retry_limit(),
            )

        return {
            "asset_id": asset_id,
            "parse_id": document_parse.id,
            "status": document_parse.status,
        }
    except Retry:
        raise
    except (
        Exception
    ) as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        failure = classify_task_exception(exc)
        if _should_retry(self, failure.retryable):
            retry_snapshot, delay = _build_task_retry_snapshot(self)
            _mark_parse_retry_pending(
                asset_id, retry_snapshot, failure.normalized_message
            )
            logger.warning(
                "解析任务异常重试: asset_id=%s attempt=%s max_retries=%s error_code=%s",
                asset_id,
                retry_snapshot["attempt"],
                retry_snapshot["max_retries"],
                failure.error_code,
            )
            raise self.retry(exc=exc, countdown=delay, max_retries=_retry_limit())

        logger.exception("解析任务执行失败: asset_id=%s", asset_id, exc_info=exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.workers.tasks.enqueue_build_asset_kb")
def enqueue_build_asset_kb(self: Task, asset_id: str) -> dict[str, str | int | None]:
    """执行资产知识库构建任务。"""
    db = SessionLocal()
    try:
        return run_asset_kb_pipeline(db, asset_id, retry_meta=_retry_context(self))
    except Retry:
        raise
    except (
        Exception
    ) as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        failure = classify_task_exception(exc)
        if _should_retry(self, failure.retryable):
            retry_snapshot, delay = _build_task_retry_snapshot(self)
            _mark_kb_retry_pending(asset_id)
            logger.warning(
                "知识库构建进入自动重试: asset_id=%s attempt=%s max_retries=%s error_code=%s",
                asset_id,
                retry_snapshot["attempt"],
                retry_snapshot["max_retries"],
                failure.error_code,
            )
            raise self.retry(exc=exc, countdown=delay, max_retries=_retry_limit())

        logger.exception("知识库构建失败: asset_id=%s", asset_id, exc_info=exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.workers.tasks.enqueue_generate_asset_mindmap")
def enqueue_generate_asset_mindmap(self: Task, asset_id: str) -> dict[str, str | int]:
    """执行资产导图生成任务。"""
    db = SessionLocal()
    try:
        return run_asset_mindmap_pipeline(db, asset_id, retry_meta=_retry_context(self))
    except Retry:
        raise
    except (
        Exception
    ) as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        failure = classify_task_exception(exc)
        if _should_retry(self, failure.retryable):
            retry_snapshot, delay = _build_task_retry_snapshot(self)
            _mark_mindmap_retry_pending(
                asset_id, retry_snapshot, failure.normalized_message
            )
            logger.warning(
                "导图生成进入自动重试: asset_id=%s attempt=%s max_retries=%s error_code=%s",
                asset_id,
                retry_snapshot["attempt"],
                retry_snapshot["max_retries"],
                failure.error_code,
            )
            raise self.retry(exc=exc, countdown=delay, max_retries=_retry_limit())

        logger.exception("导图生成失败: asset_id=%s", asset_id, exc_info=exc)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.workers.tasks.enqueue_generate_asset_slide_tts")
def enqueue_generate_asset_slide_tts(
    self: Task,
    asset_id: str,
    slide_key: str,
) -> dict[str, str | int | float]:
    """执行资产指定页面的 TTS 生成任务。"""
    db = SessionLocal()
    try:
        return run_asset_slide_tts_pipeline(db, asset_id=asset_id, slide_key=slide_key)
    except Retry:
        raise
    except Exception as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        failure = classify_task_exception(exc)
        if _should_retry(self, failure.retryable):
            retry_snapshot, delay = _build_task_retry_snapshot(self)
            _mark_tts_retry_pending(
                asset_id=asset_id,
                slide_key=slide_key,
                retry_snapshot=retry_snapshot,
                error_message=failure.normalized_message,
                error_code=failure.error_code,
            )
            logger.warning(
                "TTS 任务进入自动重试: asset_id=%s slide_key=%s attempt=%s max_retries=%s error_code=%s",
                asset_id,
                slide_key,
                retry_snapshot["attempt"],
                retry_snapshot["max_retries"],
                failure.error_code,
            )
            raise self.retry(exc=exc, countdown=delay, max_retries=_retry_limit())

        logger.exception(
            "TTS 任务执行失败且不再重试: asset_id=%s slide_key=%s",
            asset_id,
            slide_key,
            exc_info=exc,
        )
        raise
    finally:
        db.close()
