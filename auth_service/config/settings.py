"""
Django settings for auth_service.

We use Django ONLY for:
  - ORM models (User, RefreshToken)
  - Migrations (makemigrations, migrate)

We do NOT use:
  - Django views, URLs, templates, middleware, admin
  - Django's built-in User model (we write our own)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env file into os.environ
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────
# This key signs JWTs. Keep it secret. Never hardcode it.
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-dev-key-change-in-production")

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

# ──────────────────────────────────────────────
# Apps
# ──────────────────────────────────────────────
# Only register apps that have models we want in the DB.
# No django.contrib.admin — we don't need the admin UI.
INSTALLED_APPS = [
    "django.contrib.contenttypes",  # Required by Django ORM internally
    "django.contrib.auth",          # Required for content types to work
    "apps.users.apps.UsersConfig",                 # Our users app — where User and RefreshToken live
]

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
# Parse DATABASE_URL from environment.
# Example: postgresql://postgres:password@localhost:5432/auth_db
_db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/auth_db")

# Split the URL into Django's expected format
# postgresql://USER:PASSWORD@HOST:PORT/NAME
_db_url = _db_url.replace("postgresql://", "")
_user_pass, _host_name = _db_url.split("@")
_user, _password = _user_pass.split(":")
_host_port, _name = _host_name.split("/")

if ":" in _host_port:
    _host, _port = _host_port.split(":")
else:
    _host, _port = _host_port, "5432"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _name,
        "USER": _user,
        "PASSWORD": _password,
        "HOST": _host,
        "PORT": _port,
    }
}

# ──────────────────────────────────────────────
# Misc Django requirements
# ──────────────────────────────────────────────
# Django requires this even when not using views
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Required for Django to know where the settings module is
# Used by manage.py and migration commands