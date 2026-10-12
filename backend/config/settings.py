"""Django settings for the PharmaSuite backend."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.branches",
    "apps.audit",
    "apps.catalog",
    "apps.dashboard",
    "apps.inventory",
    "apps.accounting",
    "apps.suppliers",
    "apps.purchases",
    "apps.sales",
    "apps.payments",
    "apps.representatives",
    "apps.doctors",
    "apps.reports",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://mbappi@localhost:5432/erp_dev",
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": env("THROTTLE_USER_RATE", default="3000/hour"),
        "anon": env("THROTTLE_ANON_RATE", default="120/hour"),
        "login": env("THROTTLE_LOGIN_RATE", default="20/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "PharmaSuite API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_ALLOW_CREDENTIALS = True

REFRESH_COOKIE_NAME = env("REFRESH_COOKIE_NAME", default="erp_refresh")
REFRESH_COOKIE_SECURE = env.bool("REFRESH_COOKIE_SECURE", default=not DEBUG)
REFRESH_COOKIE_PATH = "/api/v1/auth/"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not DEBUG:
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    # SSL terminates at the reverse proxy (nginx on the VPS); trust its header
    # so Django doesn't redirect-loop on "insecure" requests.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/5")
CACHE_URL = env("CACHE_URL", default="redis://localhost:6379/6")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_URL,
    }
}
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "heartbeat-every-5-minutes": {
        "task": "apps.common.tasks.heartbeat",
        "schedule": 300.0,
    },
    "daily-stock-alerts": {
        "task": "apps.common.tasks.daily_stock_alerts",
        "schedule": 8 * 60 * 60,  # 08:00 local
    },
    "daily-due-alerts": {
        "task": "apps.common.tasks.daily_due_alerts",
        "schedule": 9 * 60 * 60,  # 09:00 local
    },
    "visit-reminders": {
        "task": "apps.common.tasks.visit_reminders",
        "schedule": 18 * 60 * 60,  # 18:00 local
    },
}

AUDIT_RETENTION_MONTHS = env.int("AUDIT_RETENTION_MONTHS", default=24)
TOTP_ISSUER = env("TOTP_ISSUER", default="PharmaSuite")
LOGIN_MAX_FAILED_ATTEMPTS = env.int("LOGIN_MAX_FAILED_ATTEMPTS", default=5)
LOGIN_LOCKOUT_MINUTES = env.int("LOGIN_LOCKOUT_MINUTES", default=15)
PASSWORD_HISTORY_SIZE = env.int("PASSWORD_HISTORY_SIZE", default=5)
CUSTOMER_OVERDUE_BLOCK_DAYS = env.int("CUSTOMER_OVERDUE_BLOCK_DAYS", default=30)
STOCK_ADJUSTMENT_APPROVAL_THRESHOLD = env("STOCK_ADJUSTMENT_APPROVAL_THRESHOLD", default="5000")
EXPENSE_APPROVAL_THRESHOLD = env("EXPENSE_APPROVAL_THRESHOLD", default="5000")
AUTO_APPLY_ADVANCE = env.bool("AUTO_APPLY_ADVANCE", default=False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
        }
    },
    "filters": {"request_id": {"()": "apps.common.middleware.RequestIDLogFilter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=env("SENTRY_ENVIRONMENT", default="development" if DEBUG else "production"),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        send_default_pii=False,
    )
