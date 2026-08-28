from pickle import FALSE
from corsheaders.defaults import default_headers
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

GATEWAY_SECRET = 'AwZKQwAg5nowgvSvSdb4dfPZSC6eM9F_7XH6gokrJEtB93jXEsTJTmYKQGR7xUNn0ns'

SECRET_KEY = 'django-insecure-gateway-key-simple-123'

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

DEBUG = True
ALLOWED_HOSTS = [
    '*',
    'localhost',
    '127.0.0.1',
    '.ngrok-free.app',
    '.ngrok.io',
    '.ngrok-free.dev',
]

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    'gateway.middleware.jwt_auth.JWTAuthMiddleware',
    'gateway.middleware.request_router.RequestRouterMiddleware',
]

ROOT_URLCONF = 'gateway.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gateway.wsgi.application'

# No database needed for gateway
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.dummy',
    }
}

# JWT Settings (MUST match your services)
JWT_SECRET = 'AwZKQwAg5nowgvSvSdb4dfPZSC6eM9F_7XH6gokrJEtB93jXEsTJTmYKQGR7xUNn0ns'
JWT_ALGORITHM = 'HS256'

# Service URLs
SERVICES = {
    'account': os.environ.get('ACCOUNT_SERVICE_URL', 'http://localhost:8000'),
    'course': os.environ.get('COURSE_SERVICE_URL', 'http://localhost:8001'),
    'gateway': os.environ.get('GATEWAY_URL', 'https://marielle-subchondral-rex.ngrok-free.dev'),
    'summarizer': os.environ.get('SUMMARIZER_SERVICE_URL', 'http://localhost:8003'),
    'chatbot': os.environ.get('CHATBOT_SERVICE_URL', 'http://localhost:8004'),
    'notifications': os.environ.get('NOTIFICATION_SERVICE_URL', 'http://localhost:8005'),  #AYO
}



# Public endpoints (no auth required)
PUBLIC_ENDPOINTS = [
    '/api/signup/',
    '/api/login/',
    '/health/',
    '/api/decode-token/',
    '/api/register-initiate/',
]



CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://marielle-subchondral-rex.ngrok-free.dev",
]


CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-gateway-secret',
    'x-student-id',
    'x-user-id',
    'x-username',
    'authorization',
    'ngrok-skip-browser-warning',
    "content-type",
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'