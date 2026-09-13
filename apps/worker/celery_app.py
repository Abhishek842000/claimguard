from celery import Celery
from claimguard.config import get_settings

settings = get_settings()

celery_app = Celery(
    "claimguard",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_default_queue="claims",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
)
celery_app.autodiscover_tasks(["apps.worker"])

# Explicit import so `-A apps.worker.celery_app:celery_app` always registers tasks.
from apps.worker import tasks as _tasks  # noqa: E402,F401
