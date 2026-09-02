from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from Course.services.rag_client import (
    RAGClientError,
    send_for_rag_ingestion,
)


class RAGClientTests(SimpleTestCase):
    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_INGESTION_TIMEOUT=60,
    )
    @patch("Course.services.rag_client.requests.post")
    def test_send_for_rag_ingestion_sends_expected_request(self, mock_post):
        response = MagicMock()
        mock_post.return_value = response

        send_for_rag_ingestion(
            lecture_id="lecture-1",
            course_id="course-1",
            student_id="student-1",
            text="Lecture content",
            source_type="lecture",
        )

        mock_post.assert_called_once_with(
            "http://rag-service:8005/api/rag/ingest/",
            json={
                "lecture_text": "Lecture content",
                "lecture_id": "lecture-1",
                "course_id": "course-1",
                "student_id": "student-1",
                "source_type": "lecture",
            },
            headers={
                "X-Internal-Service-Key": "test-key",
            },
            timeout=60,
        )

        response.raise_for_status.assert_called_once_with()

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY=None,
        RAG_INGESTION_TIMEOUT=60,
    )
    def test_send_for_rag_ingestion_rejects_missing_internal_key(self):
        with self.assertRaises(RAGClientError):
            send_for_rag_ingestion(
                lecture_id="lecture-1",
                course_id="course-1",
                student_id="student-1",
                text="Lecture content",
            )

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_INGESTION_TIMEOUT=60,
    )
    @patch("Course.services.rag_client.requests.post")
    def test_send_for_rag_ingestion_wraps_request_failure(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException(
            "connection failed"
        )

        with self.assertRaises(RAGClientError):
            send_for_rag_ingestion(
                lecture_id="lecture-1",
                course_id="course-1",
                student_id="student-1",
                text="Lecture content",
            )