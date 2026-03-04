import logging

from app.db.session import SessionLocal
from app.services.document_parse_service import run_parse_pipeline
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
