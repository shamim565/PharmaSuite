import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def health(request):
    return JsonResponse({"status": "ok", "service": "pharmasuite-api"})


class DeepHealthView(APIView):
    """Checks database, Redis and Celery worker availability."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        checks: dict[str, str] = {}
        healthy = True

        try:
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive
            checks["database"] = f"error: {exc}"
            healthy = False

        try:
            import redis

            client = redis.from_url(settings.REDIS_URL)
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # pragma: no cover - defensive
            checks["redis"] = f"error: {exc}"
            healthy = False

        try:
            from config.celery import app as celery_app

            replies = celery_app.control.ping(timeout=0.5)
            checks["celery"] = "ok" if replies else "no workers responding"
        except Exception as exc:  # pragma: no cover - defensive
            checks["celery"] = f"error: {exc}"

        return JsonResponse(
            {"status": "ok" if healthy else "unhealthy", "checks": checks},
            status=200 if healthy else 503,
        )
