import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "product-service-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.products.apps.ProductsConfig",
]

_db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/product_db")
_db_url = _db_url.replace("postgresql://", "")
_user_pass, _host_name = _db_url.split("@")
_user, _password = _user_pass.split(":")
_host_port, _name = _host_name.split("/")
_host, _port = (_host_port.split(":") if ":" in _host_port else (_host_port, "5432"))

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"