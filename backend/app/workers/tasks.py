import logging

from app.db.session import SessionLocal
from app.services import run_asset_mindmap_pipeline
from app.services.document_parse_service import run_parse_pipeline
from app.services.retrieval_service import enqueue_asset_chunk_rebuild, run_asset_kb_pipeline
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """最小演示任务，用于确认 Celery Worker 可以正常注册任务。"""
    return "pong"


@celery_app.task(name="app.workers.tasks.enqueue_parse_asset")
def enqueue_parse_asset(asset_id: str) -> dict[str, str]:
    """执行资产解析任务。"""
    db = SessionLocal()
    try:
        document_parse = run_parse_pipeline(db, asset_id)
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
    except Exception as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        logger.exception("解析任务执行失败: asset_id=%s", asset_id, exc_info=exc)
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.enqueue_build_asset_kb")
def enqueue_build_asset_kb(asset_id: str) -> dict[str, str | int | None]:
    """执行资产知识库构建任务。"""
    db = SessionLocal()
    try:
        return run_asset_kb_pipeline(db, asset_id)
    except Exception as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        logger.exception("知识库构建失败: asset_id=%s", asset_id, exc_info=exc)
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.enqueue_generate_asset_mindmap")
def enqueue_generate_asset_mindmap(asset_id: str) -> dict[str, str | int]:
    """执行资产导图生成任务。"""
    db = SessionLocal()
    try:
        return run_asset_mindmap_pipeline(db, asset_id)
    except Exception as exc:  # pragma: no cover - Celery 任务需要把异常继续抛出给 Worker
        logger.exception("导图生成失败: asset_id=%s", asset_id, exc_info=exc)
        raise
    finally:
        db.close()
