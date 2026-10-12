#!/bin/sh
set -e

# PharmaSuite has no django.contrib.staticfiles (no admin / no static assets),
# so there is deliberately no collectstatic here.
python manage.py migrate --noinput

exec "$@"
