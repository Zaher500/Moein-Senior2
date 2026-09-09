import requests
from django.conf import settings


class RAGClientError(Exception):
    pass


def retrieve_context(
    student_id: str,
    query: str,
    course_id: str | None = None,
    lecture_id: str | None = None,
    top_k: int = 5,
) -> dict:
    if not settings.RAG_INTERNAL_API_KEY:
        raise RAGClientError(
            "RAG internal API key is not configured."
        )

    url = f"{settings.RAG_SERVICE_URL.rstrip('/')}/api/rag/retrieve/"

    payload = {
        "student_id": str(student_id),
        "query": query,
        "top_k": top_k,
    }

    if course_id is not None:
        payload["course_id"] = str(course_id)

    if lecture_id is not None:
        payload["lecture_id"] = str(lecture_id)

    headers = {
        "X-Internal-Service-Key": settings.RAG_INTERNAL_API_KEY,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=settings.RAG_RETRIEVAL_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RAGClientError(
            "Failed to retrieve context from RAG service."
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise RAGClientError(
            "RAG service returned an invalid JSON response."
        ) from exc
