import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_asgi_application()

from rag.services.embedding_service import EmbeddingService

EmbeddingService.warm_up()
