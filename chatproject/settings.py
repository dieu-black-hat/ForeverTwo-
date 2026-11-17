"""
Settings for the ForeverTwo chat project.

Everything that changes between your laptop and a live server (secret key,
debug mode, database, allowed hosts) is read from ENVIRONMENT VARIABLES.
Locally you can put them in a `.env` file (copy `.env.example`).
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a .env file if python-dotenv is installed (optional).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------
SITE_NAME = os.environ.get("SITE_NAME", "ForeverTwo")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-in-production")
DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Render.com sets this automatically, so the app "just works" there.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

if not DEBUG and SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("Set the DJANGO_SECRET_KEY environment variable before running with DEBUG=False.")

# --- Apps -------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves CSS/JS on the live server
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "chat.middleware.ForcePasswordChangeMiddleware",
]

ROOT_URLCONF = "chatproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "chat.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "chatproject.wsgi.application"

# --- Database ---------------------------------------------------------------
# SQLite by default. Set DATABASE_URL (e.g. a PostgreSQL URL) to use another DB.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# The admin account created automatically by `python manage.py migrate`
# (only if no user with this name exists yet). Override in .env if you like.
# ⚠️ Change this password after your first login – the code is public on GitHub!
DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Hustler")
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Hustler@12345")

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# --- Language & time --------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "Africa/Kigali")
USE_I18N = True
USE_TZ = True

# --- Static files (CSS, JS) -------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# --- Security for the live server -------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# --- Uploaded files (photos, videos, documents, voice notes) ----------------
# Files are stored in MEDIA_ROOT but are NOT public: they are sent through the
# `message_file` view, which checks that you are allowed in the room.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
FILE_UPLOAD_PERMISSIONS = 0o644

# --- Chat behaviour ---------------------------------------------------------
CHAT_MAX_MESSAGE_LENGTH = 2000
CHAT_HISTORY_SIZE = 100  # how many past messages to load when opening a room
CHAT_ONLINE_SECONDS = 60  # a user counts as "online" if seen within this time

# Upload size limits in megabytes
CHAT_MAX_IMAGE_MB = int(os.environ.get("CHAT_MAX_IMAGE_MB", 10))
CHAT_MAX_VIDEO_MB = int(os.environ.get("CHAT_MAX_VIDEO_MB", 100))
CHAT_MAX_FILE_MB = int(os.environ.get("CHAT_MAX_FILE_MB", 25))
CHAT_MAX_VOICE_MB = 10
CHAT_MAX_VOICE_SECONDS = 300  # 5 minutes

# --- Audio / video calls (WebRTC) ---------------------------------------------
# STUN servers help two browsers find each other. A TURN server relays the call
# when a direct connection is impossible (common on mobile data / strict Wi-Fi).
# See README → "Calls" for how to get free TURN details.
CHAT_ICE_SERVERS = [{"urls": env_list("STUN_URLS", "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302")}]
if os.environ.get("TURN_URLS"):
    CHAT_ICE_SERVERS.append(
        {
            "urls": env_list("TURN_URLS"),
            "username": os.environ.get("TURN_USERNAME", ""),
            "credential": os.environ.get("TURN_CREDENTIAL", ""),
        }
    )
