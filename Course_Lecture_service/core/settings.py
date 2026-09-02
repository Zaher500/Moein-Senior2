from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

SERVICES = {
    'account': os.environ.get('ACCOUNT_SERVICE_URL', 'http://localhost:8000'),
    'course': os.environ.get('COURSE_SERVICE_URL', 'http://localhost:8001'),
    'gateway': os.environ.get('GATEWAY_URL', 'https://marielle-subchondral-rex.ngrok-free.dev'),
    'summarizer': os.environ.get('SUMMARIZER_SERVICE_URL', 'https://asteroidal-rikki-craniologically.ngrok-free.dev'),
    'chatbot': os.environ.get('CHATBOT_SERVICE_URL', 'http://localhost:8004'),
}

GATEWAY_SECRET = 'AwZKQwAg5nowgvSvSdb4dfPZSC6eM9F_7XH6gokrJEtB93jXEsTJTmYKQGR7xUNn0ns'

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-gb+j+njzg_qzb_0lc2hqiail_zt+b7fs@jyg-!3^)cg(a4f8je'

# Media files (Uploads)
MEDIA_URL = '/media/'  # URL prefix for media files
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Path to media directory

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok.io',
    'https://*.ngrok-free.app',
    'https://*.ngrok-free.dev',
    'http://localhost:8000',
    'http://localhost:8001',
]


ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".ngrok-free.app",    
    ".ngrok.io",          
    ".ngrok-free.dev",    
]


SUMMARIZATION_SERVICE = {
    'base_url': 'https://asteroidal-rikki-craniologically.ngrok-free.dev',
    'timeout': 60
}

CHATBOT_SERVICE = {
    "base_url": "http://127.0.0.1:8000/api",
    "timeout": 60,
}


RAG_SERVICE_URL = os.getenv(
    "RAG_SERVICE_URL",
    "http://localhost:8005",
)

RAG_INTERNAL_API_KEY = os.getenv("RAG_INTERNAL_API_KEY")

RAG_INGESTION_TIMEOUT = int(
    os.getenv("RAG_INGESTION_TIMEOUT", "60")
)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'Course',
]


REST_FRAMEWORK = {
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',       
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ]
}

# JWT Settings (MUST match Account service)
JWT_SECRET = 'AwZKQwAg5nowgvSvSdb4dfPZSC6eM9F_7XH6gokrJEtB93jXEsTJTmYKQGR7xUNn0ns'
JWT_ALGORITHM = 'HS256'
JWT_EXP_DELTA_SECONDS = 86400



MIDDLEWARE = [
    # 'Course.middleware.GatewaySecretMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True


ROOT_URLCONF = 'core.urls'

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

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'course_lecture_service',
        'USER': 'root',
        'PASSWORD': 'Zaher.0968271107',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
