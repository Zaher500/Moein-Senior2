from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ChatBot.services.rag_client import (
    RAGClientError,
    retrieve_context,
)

class RAGClientTests(SimpleTestCase):
    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    @patch("ChatBot.services.rag_client.requests.post")
    def test_retrieve_context_sends_expected_request(self, mock_post):
        response = MagicMock()
        response.json.return_value = {
            "chunks": [],
            "context_text": "",
            "sources": [],
        }
        mock_post.return_value = response

        result = retrieve_context(
            student_id="student-1",
            query="What is RAG?",
            course_id="course-1",
            lecture_id="lecture-1",
            top_k=5,
        )

        self.assertEqual(
            result,
            {
                "chunks": [],
                "context_text": "",
                "sources": [],
            },
        )

        mock_post.assert_called_once_with(
            "http://rag-service:8005/api/rag/retrieve/",
            json={
                "student_id": "student-1",
                "query": "What is RAG?",
                "top_k": 5,
                "course_id": "course-1",
                "lecture_id": "lecture-1",
            },
            headers={
                "X-Internal-Service-Key": "test-key",
            },
            timeout=15,
        )

        response.raise_for_status.assert_called_once_with()

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY=None,
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    def test_retrieve_context_rejects_missing_internal_key(self):
        with self.assertRaises(RAGClientError):
            retrieve_context(
                student_id="student-1",
                query="What is RAG?",
            )

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    @patch("ChatBot.services.rag_client.requests.post")
    def test_retrieve_context_wraps_request_failure(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException(
            "connection failed"
        )

        with self.assertRaises(RAGClientError):
            retrieve_context(
                student_id="student-1",
                query="What is RAG?",
            )

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    @patch("ChatBot.services.rag_client.requests.post")
    def test_retrieve_context_rejects_invalid_json(self, mock_post):
        response = MagicMock()
        response.json.side_effect = ValueError("invalid json")
        mock_post.return_value = response

        with self.assertRaises(RAGClientError):
            retrieve_context(
                student_id="student-1",
                query="What is RAG?",
            )
