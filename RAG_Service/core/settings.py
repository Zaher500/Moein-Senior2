import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development only. Production should provide environment variables
# through the deployment environment.
load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable is required.")


DEBUG = os.getenv("DEBUG", "False").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1",
    ).split(",")
    if host.strip()
]


HF_TOKEN = os.getenv("HF_TOKEN")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "BAAI/bge-m3",
)

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))

MILVUS_HOST = os.getenv(
    "MILVUS_HOST",
    "localhost",
)

MILVUS_PORT = os.getenv(
    "MILVUS_PORT",
    "19530",
)

MILVUS_COLLECTION = os.getenv(
    "MILVUS_COLLECTION",
    "chatbot_lecture_chunks",
)

MILVUS_METRIC_TYPE = os.getenv(
    "MILVUS_METRIC_TYPE",
    "COSINE",
)

INSTALLED_APPS = [
    "rest_framework",
    "rag.apps.RagConfig",
]


RAG_INTERNAL_API_KEY = os.getenv("RAG_INTERNAL_API_KEY")


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]


ROOT_URLCONF = "core.urls"

TEMPLATES = []

WSGI_APPLICATION = "core.wsgi.application"


DATABASES = {}


AUTH_PASSWORD_VALIDATORS = []


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "UNAUTHENTICATED_USER": None,
}


# Defensive defaults for an API-only internal service.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
