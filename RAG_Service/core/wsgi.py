import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()

from rag.services.embedding_service import EmbeddingService

EmbeddingService.warm_up()
