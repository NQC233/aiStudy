from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "paper_learning",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=max(settings.celery_worker_prefetch_multiplier, 1),
    broker_transport_options={
        "visibility_timeout": max(settings.celery_visibility_timeout_sec, 300),
    },
)

celery_app.autodiscover_tasks(["app.workers"])
