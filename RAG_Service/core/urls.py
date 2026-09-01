from django.urls import include, path


urlpatterns = [
    path("api/rag/", include("rag.urls")),
]
