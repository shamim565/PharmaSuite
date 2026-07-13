import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.common.tasks.heartbeat")
def heartbeat() -> dict:
    """Periodic liveness task; also used to smoke-test workers."""
    timestamp = timezone.now().isoformat()
    logger.info("celery heartbeat at %s", timestamp)
    return {"status": "ok", "timestamp": timestamp}
