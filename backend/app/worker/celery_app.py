from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from app.core.config import settings
from app.db.mongo import connect_to_mongo_sync, close_mongo_connection_sync

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URI,
    backend=settings.REDIS_URI,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Late acks + one prefetched task: a crashed worker's job is redelivered, and
    # long LLM jobs are not hoarded behind each other.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Must exceed the longest retry countdown (300s cap + jitter) and the task time
    # limit, otherwise Redis redelivers delayed retries as duplicates.
    broker_transport_options={"visibility_timeout": 3600},
)

@worker_process_init.connect
def init_worker(**kwargs):
    connect_to_mongo_sync()

@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    close_mongo_connection_sync()
