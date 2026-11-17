#!/usr/bin/env bash
# Build script used by Render.com (runs every time you deploy).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Optional: create an admin account automatically if these env vars are set:
# DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD (and DJANGO_SUPERUSER_EMAIL)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --no-input || true
fi
