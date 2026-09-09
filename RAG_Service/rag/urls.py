from django.urls import path

from .views import (
    HealthCheckView,
    IngestLectureView,
    RetrieveContextView,
)


urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="rag-health"),
    path("retrieve/", RetrieveContextView.as_view(), name="rag-retrieve"),
    path("ingest/", IngestLectureView.as_view(), name="rag-ingest"),
]
