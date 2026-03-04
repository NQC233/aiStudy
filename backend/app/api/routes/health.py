from fastapi import APIRouter

from app.core.config import settings
from app.workers.tasks import ping

router = APIRouter()


@router.get("/health", summary="健康检查")
async def healthcheck() -> dict[str, str]:
    """返回基础服务状态，用于验证骨架已可访问。"""
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "task_queue": ping.name,
    }
