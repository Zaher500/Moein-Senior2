import requests
from django.conf import settings


class RAGClientError(Exception):
    pass


def send_for_rag_ingestion(
    lecture_id: str,
    course_id: str,
    student_id: str,
    text: str,
    source_type: str = "lecture",
) -> None:
    if not settings.RAG_INTERNAL_API_KEY:
        raise RAGClientError(
            "RAG internal API key is not configured."
        )

    url = f"{settings.RAG_SERVICE_URL.rstrip('/')}/api/rag/ingest/"

    payload = {
        "lecture_text": text,
        "lecture_id": str(lecture_id),
        "course_id": str(course_id),
        "student_id": str(student_id),
        "source_type": source_type,
    }

    headers = {
        "X-Internal-Service-Key": settings.RAG_INTERNAL_API_KEY,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=settings.RAG_INGESTION_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RAGClientError(
            "Failed to ingest lecture into RAG service."
        ) from exc