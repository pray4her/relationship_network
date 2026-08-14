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
        beat_schedule={
            # Task name kept in sync with RELEASE_EXPIRED_RESERVATIONS_TASK_NAME
            # in tasks.py (importing it here would be circular).
            "release-expired-usage-reservations": {
                "task": "relationship_network.release_expired_usage_reservations",
                "schedule": 300.0,
            },
            # Task name kept in sync with EXPIRE_DUE_SUBSCRIPTIONS_TASK_NAME
            # in tasks.py (importing it here would be circular).
            "expire-due-subscriptions": {
                "task": "relationship_network.expire_due_subscriptions",
                "schedule": 86400.0,
            },
            "schedule-due-llm-configuration-attempts": {
                "task": "relationship_network.schedule_due_llm_configuration_attempts",
                "schedule": 10.0,
                "options": {"queue": "platform"},
            },
            "recover-expired-llm-configuration-leases": {
                "task": "relationship_network.recover_expired_llm_configuration_leases",
                "schedule": 30.0,
                "options": {"queue": "platform"},
            },
            "schedule-due-job-requirement-tasks": {
                "task": "relationship_network.schedule_due_job_requirement_tasks",
                "schedule": 10.0,
                "options": {"queue": "tenant"},
            },
            "recover-expired-job-requirement-leases": {
                "task": "relationship_network.recover_expired_job_requirement_leases",
                "schedule": 30.0,
                "options": {"queue": "tenant"},
            },
            "cleanup-expired-llm-raw-responses": {
                "task": "relationship_network.cleanup_expired_llm_raw_responses",
                "schedule": 86400.0,
                "options": {"queue": "maintenance"},
            },
            # Task name kept in sync with
            # CLEANUP_EXPIRED_REQUIREMENT_INPUT_BODIES_TASK_NAME in tasks.py.
            "cleanup-expired-requirement-input-bodies": {
                "task": "relationship_network.cleanup_expired_requirement_input_bodies",
                "schedule": 86400.0,
                "options": {"queue": "maintenance"},
            },
        },
    )
    return app


celery_app = create_celery_app(WorkerSettings())
