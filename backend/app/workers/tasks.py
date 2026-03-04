from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """最小演示任务，用于确认 Celery Worker 可以正常注册任务。"""
    return "pong"
