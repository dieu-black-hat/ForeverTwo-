#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ForeverTwo – one-command setup for PythonAnywhere.
#
# Run it in a PythonAnywhere Bash console, inside the project folder:
#     bash pythonanywhere_setup.sh          (uses Python 3.12)
#     bash pythonanywhere_setup.sh 3.11     (or choose another version)
#
# It is safe to run again later (for example after `git pull`) to update the site.
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

PROJECT_DIR="$(pwd)"
DOMAIN="${USER}.pythonanywhere.com"
VENV="$HOME/.virtualenvs/forevertwo"
WANTED="${1:-3.12}"

PY="python${WANTED}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "!! python${WANTED} not found. Available: $(ls /usr/bin | grep -E '^python3\.[0-9]+$' | tr '\n' ' ')"
  exit 1
fi

echo "==> 1/5  Creating virtual environment with $PY (first time takes a minute)"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> 2/5  Installing packages"
pip install -q --upgrade pip
pip install -q -r requirements.txt || pip install -q "Django>=5.2,<6.0" whitenoise gunicorn dj-database-url python-dotenv Pillow

echo "==> 3/5  Writing settings (.env)"
if [ ! -f .env ]; then
  SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
  cat > .env <<EOF
SITE_NAME=ForeverTwo
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=${SECRET}
DJANGO_ALLOWED_HOSTS=${DOMAIN}
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN}
TIME_ZONE=Africa/Kigali
EOF
  echo "    created .env for ${DOMAIN}"
else
  echo "    .env already exists – keeping it"
fi

echo "==> 4/5  Building database and static files"
python manage.py migrate --no-input
python manage.py collectstatic --no-input -v0

echo "==> 5/5  Connecting the website"
WSGI="/var/www/${USER}_pythonanywhere_com_wsgi.py"
if [ -f "$WSGI" ]; then
  cat > "$WSGI" <<EOF
import os, sys
path = "${PROJECT_DIR}"
if path not in sys.path:
    sys.path.insert(0, path)
os.environ["DJANGO_SETTINGS_MODULE"] = "chatproject.settings"
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
EOF
  touch "$WSGI"   # touching the WSGI file reloads the site
  echo "    WSGI file updated and site reloaded"
else
  echo "    !! No web app yet. Go to the Web tab -> Add a new web app ->"
  echo "       Manual configuration -> Python ${WANTED}, then run this script again."
fi

cat <<EOF

=====================================================================
 Almost done! On the PythonAnywhere "Web" tab, check these (once):

   Python version : ${WANTED}
   Virtualenv     : ${VENV}
   Static files   : URL /static/  ->  ${PROJECT_DIR}/staticfiles
   Force HTTPS    : ON

 Then click the green "Reload" button.

 Your chat link to share with friends:
     https://${DOMAIN}

 Log in as:  Hustler  /  Hustler@12345
 ⚠️  Then change that password right away (🔑 icon in the sidebar),
     because the default password is written in the public code.
=====================================================================
EOF
