from celery import Celery

from relationship_network_api.config import WorkerSettings


def create_celery_app(settings: WorkerSettings) -> Celery:
    app = Celery(
        "relationship_network",
        broker=str(settings.celery_broker_url),
        backend=str(settings.celery_result_backend),
    )
    app.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        result_accept_content=["json"],
        result_serializer="json",
        task_serializer="json",
        task_track_started=True,
        timezone="UTC",
    )
    return app


celery_app = create_celery_app(WorkerSettings())
